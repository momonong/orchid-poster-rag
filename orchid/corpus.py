import hashlib
import json
import re
from pathlib import Path


def load_corpus(path: Path):
    items = json.loads(path.read_text(encoding="utf-8"))
    if not items or len({item["id"] for item in items}) != len(items):
        raise ValueError("語料為空或來源 ID 重複")
    for item in items:
        for key in ("id", "text", "title", "document", "section", "kind", "version"):
            if not item.get(key):
                raise ValueError(f"語料缺少 {key}")
    return items


def corpus_hash(items):
    return hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def verify_sources(settings):
    sources = json.loads((settings.data / "sources.json").read_text(encoding="utf-8"))
    for name in ("poster", "paper"):
        item = sources[name]
        path = (settings.root / item["path"]).resolve()
        if not path.is_relative_to(settings.root.resolve()):
            raise ValueError("來源路徑超出專案")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("原始 PDF 已變更，請重新校對語料再入庫")
    for item in load_corpus(settings.data / "evidence.json"):
        if item["document"] in {"poster", "paper"} and item.get("source_sha256") != sources[item["document"]]["sha256"]:
            raise ValueError("語料未綁定目前來源 PDF")


def split_text(text, count_tokens, limit=480, prefix=""):
    """Split without dropping tokens; prefix is counted and never silently truncated."""
    units = re.findall(r"\S+\s*", text)
    chunks, current = [], ""
    for unit in units:
        if count_tokens(prefix + current + unit) <= limit:
            current += unit
            continue
        if current.strip():
            chunks.append(current.strip())
            current = ""
        if count_tokens(prefix + unit) > limit:
            for char in unit:
                if count_tokens(prefix + current + char) > limit:
                    if not current:
                        raise ValueError("前綴已超過 embedding token 限制")
                    chunks.append(current)
                    current = ""
                current += char
        else:
            current = unit
    if current.strip():
        chunks.append(current.strip())
    return chunks


def lexical_tokens(text):
    text = text.lower()
    tokens = re.findall(r"[a-z][a-z0-9_]*|\d+(?:\.\d+)?", text)
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens
