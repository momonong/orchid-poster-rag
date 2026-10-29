import pytest

from orchid import generation


def candidates():
    build = getattr(generation, "paragraph_candidates", None)
    assert callable(build), "English output needs complete reviewed paragraph candidates"
    return build([
        {"id": "E01_1", "text": "The model value is 0.03 under these conditions.\n\nA separate limitation remains.",
         "document": "paper", "figure": "Fig. 2", "page": 1, "section": "Results",
         "text_provenance": "reviewed_summary_translation_not_verbatim", "original_source_chunk": "raw excerpt"},
        {"id": "E01_2", "text": "The model value is 0.03 under these conditions.\n\nA separate limitation remains.",
         "document": "paper", "section": "Results"},
        {"id": "E02", "text": "Another complete condition is retained.", "document": "poster", "section": "Methods"},
    ])


def selection(source="E01_1", index=0):
    return {"source_id": source, "paragraph_index": index}


def decode(value, counter=len):
    helper = getattr(generation, "selected_answer", None)
    assert callable(helper), "Only validated paragraph selections may enter English answers"
    return helper(value, candidates(), counter)


def test_selected_full_paragraphs_are_returned_verbatim_with_request_local_citations():
    result = decode({"status": "answered", "selections": [selection(), selection("E02")]})
    assert result == {"status": "answered", "answer":
        "The model value is 0.03 under these conditions. [E01_1]\n\nAnother complete condition is retained. [E02]"}
    rows = candidates()
    assert rows[0]["paragraphs"] == [
        {"paragraph_index": 0, "text": "The model value is 0.03 under these conditions."},
        {"paragraph_index": 1, "text": "A separate limitation remains."},
    ]
    assert "original_source_chunk" not in rows[0]
    assert rows[0]["figure"] == "Fig. 2"


@pytest.mark.parametrize("value", [
    {"status": "answered", "answer": "Invented 0.99 [E01_1]", "selections": [selection()]},
    {"status": "answered", "selections": [{**selection(), "text": "Invented content"}]},
    {"status": "answered", "selections": [selection("FAKE")]},
    {"status": "answered", "selections": [selection("E01")]},
    {"status": "answered", "selections": [selection(index=True)]},
    {"status": "answered", "selections": [selection(index=0.0)]},
    {"status": "answered", "selections": [selection(index="0")]},
    {"status": "answered", "selections": [selection(index=-1)]},
    {"status": "answered", "selections": [selection(index=2)]},
    {"status": "answered", "selections": [selection(), selection()]},
    {"status": "answered", "selections": [selection(), selection("E01_2")]},
    {"status": "answered", "selections": [selection(), selection(index=1), selection("E02")]},
    {"status": "answered", "selections": []},
    {"status": "answered", "selections": "E01_1"},
    {"status": "unknown", "selections": [selection()]},
    {"status": "unknown", "answer": "generated", "selections": []},
    {"status": "anything", "selections": []},
    {"status": ["answered"], "selections": []},
])
def test_forged_generated_duplicate_or_invalid_selections_are_rejected(value):
    with pytest.raises(ValueError):
        decode(value)


def test_unknown_accepts_only_empty_selections_and_never_generated_answer_text():
    assert decode({"status": "unknown", "selections": []}) == {"status": "unknown", "answer": ""}


def test_two_different_paragraphs_of_same_canonical_source_remain_allowed():
    result = decode({"status": "answered", "selections": [selection(), selection("E01_2", 1)]})
    assert result["answer"] == (
        "The model value is 0.03 under these conditions. [E01_1]\n\nA separate limitation remains. [E01_2]")


def test_answer_token_limit_is_checked_after_citations_without_truncation():
    value = {"status": "answered", "selections": [selection()]}
    assert decode(value, lambda text: 512)["answer"] == "The model value is 0.03 under these conditions. [E01_1]"
    with pytest.raises(OverflowError):
        decode(value, lambda text: 513)
