import json

import pytest

from orchid import generation
from orchid.config import ROOT


@pytest.mark.parametrize("answer", [
    "必須同時降低活化者 PeMYB11 的降解率 μ_A 才能產生較大且融合的紫色斑塊 [P08_1]。",
    "模擬結果證明 miR858 對斑點形成至關重要 [P10_2]。",
    "模型是透過降低 μ_A 來代理 miR858 功能缺失的效果 [P10_1]。",
    "只有合併提高 G_A 與降低 µ_A，才能形成融合斑塊 [P11]。",
])
def test_live_smoke_overclaims_are_rejected(answer):
    guard = getattr(generation, "validate_claim_scope", None)
    assert callable(guard), "real smoke failures need a focused scientific scope guard"
    assert not guard(answer)


@pytest.mark.parametrize("answer", [
    "在這組模型條件下，合併提高 G_A 與降低 µ_A 的模擬可重現較大融合斑塊 [P11]。",
    "D_H 必須大於 D_A，合併調整 G_A 與 µ_A 可重現融合斑塊；這仍是模型預測 [P03]。",
    "降低 miR858 表達並不等同功能缺失或 knockout，模擬仍需實驗驗證 [P10]。",
    "無法由這些模擬證明 miR858 對斑點形成至關重要 [P10]。",
])
def test_scoped_simulation_and_real_model_conditions_remain_allowed(answer):
    guard = getattr(generation, "validate_claim_scope", None)
    assert callable(guard)
    assert guard(answer)


def test_paper_sources_link_to_real_poster_topics():
    rows = {row["id"]: row for row in json.loads((ROOT / "data/evidence.json").read_text(encoding="utf-8"))}
    for source in ("P08", "P09", "P10", "P11", "P15"):
        assert "clue2" in rows[source].get("poster_sections", []), source
    for source in ("P12", "P13"):
        assert "clue3" in rows[source].get("poster_sections", []), source
    for source in ("P03", "P04", "P05", "P07"):
        assert "clue1" in rows[source].get("poster_sections", []), source


def test_ga_2712_expression_estimate_is_separate_from_promoter_assay():
    item = next(row for row in json.loads((ROOT / "data/evidence.json").read_text(encoding="utf-8"))
                if row["id"] == "P09")
    assert "2.712" in item["title"] and "表達" in item["title"]
    parts = item["text"].split("\n\n")
    assay = next(part for part in parts if part.startswith("啟動子實驗"))
    expression = next(part for part in parts if part.startswith("品種間表達量"))
    assert all(value in assay for value in ("dual luciferase", "0.1632", "0.66"))
    assert "33.9" not in assay and "2.712" not in assay
    assert all(value in expression for value in ("33.9", "0.08", "2.712"))
    assert "33.9-fold" in item["original_excerpt"] and "dual luciferase" in item["original_excerpt"]
    assert any("P11" in part and "0.01" in part for part in parts)
