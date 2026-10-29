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
def test_inhibitor_self_activation_misstatement_is_rejected_without_rejecting_correct_activation():
    from orchid.generation import validate_claim_scope
    invalid = [
        'PeMYBx 作為抑制者 H 透過 G_H 活化自身並抑制 A 的合成 [P03]。',
        '抑制者 H 會自我活化 [P03]。',
        'G_H 是抑制者的自我活化強度 [P04]。',
        'PeMYBx self-activates in the model [P03].',
        'PeMYBx 活化自身，但這不代表全部分子機制 [P03]。',
    ]
    valid = [
        'PeMYB11 透過 G_A 自我活化，並以 G_H 活化 PeMYBx；PeMYBx 抑制 PeMYB11 [P03]。',
        'PeMYB11 自我活化並促進抑制者 H，H 反過來抑制 PeMYB11 [P03]。',
        'PeMYBx 並沒有自我活化；G_H 是 A 活化 H 的強度 [P04]。',
        'G_H 不是 PeMYBx 自我活化，而是 A 活化 H 的強度 [P04]。',
        'PeMYBx 抑制 PeMYB11 的自我活化 [P03]。',
        'PeMYBx does not self-activate [P03].',
    ]
    for text in invalid:
        assert not validate_claim_scope(text), text
    for text in valid:
        assert validate_claim_scope(text), text
