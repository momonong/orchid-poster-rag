import json

import pytest

from orchid.config import Settings
from orchid.corpus import verify_sources


def test_index_refuses_changed_source_pdf(tmp_path):
    settings = Settings(root=tmp_path)
    settings.data.mkdir()
    for name in ("poster", "paper"):
        (tmp_path / f"{name}.pdf").write_bytes(b"changed")
    (settings.data / "sources.json").write_text(json.dumps({name: {"path": f"{name}.pdf", "sha256": "old"}
                                                           for name in ("poster", "paper")}))
    with pytest.raises(ValueError, match="PDF"):
        verify_sources(settings)


def test_real_corpus_has_traceable_originals():
    from orchid.config import ROOT
    rows = json.loads((ROOT / "data/evidence.json").read_text(encoding="utf-8"))
    assert len(rows) == 21
    for item in rows:
        assert len(item["original_excerpt"]) > 50
        assert item["locators"]
        for locator in item["locators"]:
            if "rect" in locator:
                x0, y0, x1, y1 = locator["rect"]
                assert 0 <= x0 < x1 <= 1
                assert 0 <= y0 < y1 <= 1


def test_generated_answer_cannot_invent_numeric_values():
    from orchid.generation import validate_numbers
    passages = [{"text": "D_A = 0.01，D_H = 0.5。PeMYB11、miR858 與 HORT1。"}]
    assert validate_numbers("D_A = 0.01，D_H = 0.5 [P01]", passages)
    assert not validate_numbers("D_A = 0.02 [P01]", passages)


def test_iso_date_and_same_value_numeric_formatting_are_equivalent():
    from orchid.generation import validate_numbers
    passages = [{"text": "更正於 2024-08-17 發表；設定值 0.03 與 7。"}]
    assert validate_numbers("更正於 2024 年 8 月 17 日發表 [C01]", passages)
    assert validate_numbers("設定值為 0.0300 與 7.0 [P01]", passages)


@pytest.mark.parametrize("source,answer", [
    ("D_A = -0.03", "D_A = 0.03 [P01]"),
    ("D_A = 0.03", "D_A = -0.03 [P01]"),
    ("更正於 2024-08-17", "更正於 2024 年 8 月 18 日 [C01]"),
    ("不是有效日期 2024-13-40", "2024 年 13 月 40 日 [C01]"),
])
def test_date_normalization_preserves_negative_and_invented_number_rejection(source, answer):
    from orchid.generation import validate_numbers
    assert not validate_numbers(answer, [{"text": source}])


def test_long_query_is_rejected_before_embedding():
    from orchid.retrieval import HybridIndex
    class Tokenizer:
        def encode(self, text, **kwargs):
            return list(range(len(text)))
    class Encoder:
        tokenizer = Tokenizer()
        def encode(self, *args, **kwargs):
            raise AssertionError("long query must not be silently truncated and embedded")
    index = HybridIndex.__new__(HybridIndex)
    index.ready, index.encoder = True, Encoder()
    with pytest.raises(ValueError, match="縮短"):
        index.search("花" * 600)
