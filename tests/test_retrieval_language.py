import numpy as np
import pytest
from rank_bm25 import BM25Okapi

from orchid.corpus import lexical_tokens
from orchid.retrieval import HybridIndex


class Encoder:
    def __init__(self):
        self.tokenizer = self
        self.queries = []

    def encode(self, text, **kwargs):
        if isinstance(text, str):
            return text.split()
        self.queries.extend(text)
        return np.zeros((len(text), 1))


def index():
    value = HybridIndex.__new__(HybridIndex)
    value.ready = True
    value.encoder = Encoder()
    value.chunks = [
        {"id": "threshold", "text": "花青素量測與視覺化閾值，使用 µM 濃度。", "title": "視覺化"},
        {"id": "fusion", "text": "單獨提高自我活化與斑點融合、融合斑塊的比較。", "title": "融合"},
        {"id": "diffusion", "text": "擴散係數及空間格點", "title": "方法"},
        {"id": "contacts", "text": "研究聯絡資訊", "title": "聯絡"},
    ]
    value.bm25 = BM25Okapi([lexical_tokens(row["text"] + " " + row["title"]) for row in value.chunks])
    value.vectors = np.zeros((len(value.chunks), 1))
    return value


@pytest.mark.parametrize("question, expected", [
    ("Is a micromolar anthocyanin measurement a concentration threshold?", "threshold"),
    ("Can increasing self-activation alone produce fused patterns?", "fusion"),
])
def test_english_terms_bridge_to_reviewed_chinese_without_source_selection(question, expected):
    current = index()
    results = current.search(question, language="en")
    assert results[0]["id"] == expected
    assert current.encoder.queries[0].startswith("query: " + question + " ")


def test_chinese_retrieval_keeps_original_query_without_aliases():
    current = index()
    question = "threshold 在研究中的意義是什麼？"
    current.search(question, language="zh-TW")
    assert current.encoder.queries == ["query: " + question]


def test_alias_expansion_never_bypasses_original_query_token_limit():
    current = index()
    question = " ".join(["word"] * 512 + ["threshold"])
    with pytest.raises(ValueError, match="縮短"):
        current.search(question, language="en")
    assert current.encoder.queries == []


def test_near_limit_retains_complete_original_query_when_optional_aliases_do_not_fit():
    current = index()
    question = " ".join(["word"] * 509 + ["micromolar", "measurement"])
    current.search(question, language="en")
    assert current.encoder.queries == ["query: " + question]
