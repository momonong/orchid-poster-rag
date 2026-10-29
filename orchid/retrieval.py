import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from .config import E5_MODEL, E5_REVISION
from .corpus import corpus_hash, lexical_tokens, load_corpus, split_text, verify_sources

# Query-only bilingual vocabulary bridge. No answers, source IDs or parameter values.
# The stored corpus, BM25 document tokens and vector index stay unchanged.
ENGLISH_ALIASES = (
    (r"\b(?:spot[- ]fusion|fused[- ](?:spots?|patches?|patterns?)|fusion)\b", "斑點融合 融合斑塊"),
    (r"\balone\b", "單獨"),
    (r"\bincreas(?:e|ed|ing)\b", "提高"),
    (r"\bself[- ]activation\b", "自我活化"),
    (r"\bdegradation\b", "降解"),
    (r"\bmicromolar\b", "µM"),
    (r"\banthocyanin\b", "花青素"),
    (r"\bmeasurements?\b", "量測 實測"),
    (r"\bthresholds?\b", "閾值"),
    (r"\bconcentrations?\b", "濃度"),
)


def english_query_aliases(query):
    aliases = [alias for pattern, alias in ENGLISH_ALIASES if re.search(pattern, query, re.IGNORECASE)]
    return query + " " + " ".join(aliases) if aliases else query


def encoder_path(settings):
    return settings.cache / "e5-model"


def load_encoder(settings):
    from sentence_transformers import SentenceTransformer
    path = encoder_path(settings)
    if not (path / "config.json").exists():
        raise FileNotFoundError("尚未下載 CPU embedding 模型；執行 orchid index --download")
    return SentenceTransformer(str(path), device="cpu", local_files_only=True, trust_remote_code=False)


def build_index(settings, download=False):
    verify_sources(settings)
    if download:
        from huggingface_hub import snapshot_download
        snapshot_download(E5_MODEL, revision=E5_REVISION, local_dir=encoder_path(settings),
                          ignore_patterns=["onnx/*", "openvino/*", "pytorch_model.bin", "*.h5", "*.ot"])
    encoder = load_encoder(settings)
    original = load_corpus(settings.data / "evidence.json")
    chunks = []
    count = lambda text: len(encoder.tokenizer.encode(text, add_special_tokens=True))
    for item in original:
        prefix = f"passage: {item['title']}\n"
        full_text = item["text"] + "\n\nOriginal source excerpt (PDF text extraction):\n" + item.get("original_excerpt", "")
        parts = split_text(full_text, count, 480, prefix)
        for number, part in enumerate(parts):
            chunks.append({**item, "id": item["id"] if len(parts) == 1 else f"{item['id']}_{number + 1}",
                           "text": part, "summary": item["text"], "embedding_tokens": count(prefix + part)})
    vectors = encoder.encode([f"passage: {c['title']}\n{c['text']}" for c in chunks],
                             normalize_embeddings=True, batch_size=16, show_progress_bar=True)
    settings.index.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="index-", dir=settings.index.parent))
    try:
        np.save(temp / "vectors.npy", vectors, allow_pickle=False)
        (temp / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        (temp / "manifest.json").write_text(json.dumps({"corpus_hash": corpus_hash(original),
            "model": E5_MODEL, "revision": E5_REVISION, "dimension": vectors.shape[1],
            "chunks": len(chunks), "token_limit": 480, "normalized": True}), encoding="utf-8")
        # Publish manifest last. A running service never silently reloads a half-built index.
        settings.index.mkdir(exist_ok=True)
        for name in ("vectors.npy", "chunks.json", "manifest.json"):
            os.replace(temp / name, settings.index / name)
    finally:
        shutil.rmtree(temp)
    return {"chunks": len(chunks), "max_tokens": max(c["embedding_tokens"] for c in chunks)}


class HybridIndex:
    def __init__(self, settings):
        self.settings = settings
        self.ready, self.reason = False, "尚未建立索引"
        self.chunks, self.encoder = [], None
        try:
            manifest = json.loads((settings.index / "manifest.json").read_text(encoding="utf-8"))
            corpus = load_corpus(settings.data / "evidence.json")
            verify_sources(settings)
            if manifest["corpus_hash"] != corpus_hash(corpus):
                raise ValueError("語料已更新，請重建索引")
            if manifest["model"] != E5_MODEL or manifest["revision"] != E5_REVISION:
                raise ValueError("embedding 模型版本不符，請重建索引")
            self.chunks = json.loads((settings.index / "chunks.json").read_text(encoding="utf-8"))
            self.vectors = np.load(settings.index / "vectors.npy", allow_pickle=False)
            if self.vectors.shape != (len(self.chunks), manifest["dimension"]):
                raise ValueError("索引維度不符")
            if not np.isfinite(self.vectors).all() or not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=0.01):
                raise ValueError("索引向量不合法")
            self.bm25 = BM25Okapi([lexical_tokens(c["text"] + " " + c["title"]) for c in self.chunks])
            self.encoder = load_encoder(settings)
            self.ready, self.reason = True, "CPU hybrid 索引就緒"
        except (OSError, ValueError, KeyError, ImportError):
            self.reason = "索引或 CPU embedding 模型缺少、過期或無法載入；請執行 orchid index"

    def search(self, question, history=None, top_k=4, language="zh-TW"):
        if not self.ready:
            raise RuntimeError(self.reason)
        # History can disambiguate short follow-ups, but is never inserted as source evidence.
        query = question
        if history and len(question) < 35:
            previous = next((h["content"] for h in reversed(history) if h["role"] == "user"), "")
            query = f"{previous[:200]} {question}"
        if len(self.encoder.tokenizer.encode("query: " + query, add_special_tokens=True)) > 512:
            raise ValueError("問題加上追問前文超過 embedding 長度限制，請縮短問題或清除對話後再問。")
        if language == "en":
            expanded = english_query_aliases(query)
            # Optional aliases never truncate the original or make a valid query fail.
            if len(self.encoder.tokenizer.encode("query: " + expanded, add_special_tokens=True)) <= 512:
                query = expanded
        vector = self.encoder.encode(["query: " + query], normalize_embeddings=True, show_progress_bar=False)[0]
        dense = self.vectors @ vector
        sparse = self.bm25.get_scores(lexical_tokens(query))
        scores = np.zeros(len(self.chunks))
        for values in (dense, sparse):
            for rank, index in enumerate(np.argsort(-values)[:16]):
                if values[index] > 0:
                    scores[index] += 1 / (60 + rank + 1)
        selected = np.argsort(-scores)[:top_k]
        return [{**self.chunks[i], "retrieval": {"dense": round(float(dense[i]), 4),
                 "bm25": round(float(sparse[i]), 4)}} for i in selected if scores[i] > 0]
