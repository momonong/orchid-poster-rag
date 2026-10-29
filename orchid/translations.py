import json

from .corpus import corpus_hash, load_corpus

TRANSLATION_UNAVAILABLE = "英文校對摘要譯文缺少、不完整或與研究語料版本不符"


def english_evidence(settings, passages):
    """Bind complete reviewed translations to the canonical corpus, never to query text."""
    source = load_corpus(settings.data / "evidence.json")
    source_by_id = {row["id"]: row for row in source}
    digest = corpus_hash(source)
    translated = json.loads((settings.data / "evidence.en.json").read_text(encoding="utf-8"))
    if (translated["language"] != "en" or translated["kind"] != "reviewed_summary_translation"
        or translated["source_corpus_sha256"] != digest or not isinstance(translated["items"], list)):
        raise ValueError(TRANSLATION_UNAVAILABLE)
    rows = translated["items"]
    texts = {}
    for row in rows:
        if (not isinstance(row["id"], str) or row["id"] in texts or not isinstance(row["text"], str)
            or not row["text"].strip()):
            raise ValueError(TRANSLATION_UNAVAILABLE)
        texts[row["id"]] = row["text"]
    if set(texts) != set(source_by_id):
        raise ValueError(TRANSLATION_UNAVAILABLE)
    evidence = []
    for passage in passages:
        source_id = passage["id"].split("_", 1)[0]
        if source_id not in texts or ("summary" in passage and passage["summary"] != source_by_id[source_id]["text"]):
            raise ValueError(TRANSLATION_UNAVAILABLE)
        evidence.append({"id": passage["id"], "text": texts[source_id],
            "text_provenance": "reviewed_summary_translation_not_verbatim",
            "kind": passage["kind"], "document": passage.get("document"),
            "figure": passage.get("figure"), "page": passage.get("page"), "section": passage["section"],
            "original_source_chunk": passage["text"]})
    return evidence
