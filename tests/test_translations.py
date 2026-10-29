import json
import re

import httpx
import pytest

from orchid.config import QWEN_REVISION, ROOT, Settings
from orchid.corpus import corpus_hash
from orchid.generation import ModelClient, Unavailable, validate_numbers


def fixture_data(tmp_path):
    settings = Settings(root=tmp_path)
    settings.data.mkdir()
    source = [{"id": "E01", "text": "濃度為 0.03，屬模型參數。", "title": "fixture",
               "document": "paper", "section": "Methods", "kind": "model", "version": "fixture"}]
    translation = {"language": "en", "kind": "reviewed_summary_translation",
                   "source_corpus_sha256": corpus_hash(source),
                   "items": [{"id": "E01", "text": "The concentration is 0.03, a model parameter."}]}
    (settings.data / "evidence.json").write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    (settings.data / "evidence.en.json").write_text(json.dumps(translation), encoding="utf-8")
    return settings, source, translation


@pytest.mark.parametrize("mutation", ["missing", "incomplete", "duplicate", "foreign", "blank", "outdated"])
@pytest.mark.asyncio
async def test_missing_incomplete_or_outdated_translation_is_unavailable_before_model_call(tmp_path, mutation):
    settings, source, translated = fixture_data(tmp_path)
    path = settings.data / "evidence.en.json"
    if mutation == "missing":
        path.unlink()
    else:
        if mutation == "incomplete":
            translated["items"] = []
        elif mutation == "duplicate":
            translated["items"] *= 2
        elif mutation == "foreign":
            translated["items"][0]["id"] = "OTHER"
        elif mutation == "blank":
            translated["items"][0]["text"] = " "
        else:
            source[0]["text"] = "濃度為 0.01，屬模型參數。"
            (settings.data / "evidence.json").write_text(json.dumps(source), encoding="utf-8")
        path.write_text(json.dumps(translated), encoding="utf-8")
    requests = []

    def handle(request):
        requests.append(request.url.path)
        raise AssertionError("invalid translations must not send a model request")

    model = ModelClient(settings, httpx.MockTransport(handle), len)
    with pytest.raises(Unavailable, match="英文.*譯文"):
        await model.generate("test", [], source, "en")
    assert requests == []
    await model.close()


@pytest.mark.asyncio
async def test_english_uses_bound_summary_translation_and_keeps_original_chunk(tmp_path):
    settings, source, translated = fixture_data(tmp_path)
    key = tmp_path / "key"
    key.write_text("fixture-key")
    settings.key_file = str(key)
    payloads = []

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": '{"status":"answered","selections":[{"source_id":"E01_2","paragraph_index":0}]}'}}]})

    model = ModelClient(settings, httpx.MockTransport(handle), len)
    passage = {**source[0], "id": "E01_2", "summary": source[0]["text"], "text": "Original chunk text"}
    output = await model.generate("test", [], [passage], "en")
    evidence = json.loads(payloads[0]["messages"][1]["content"].split("\n\n", 1)[0])["evidence"][0]
    assert evidence["paragraphs"] == [{"paragraph_index": 0, "text": translated["items"][0]["text"]}]
    assert output["answer"] == translated["items"][0]["text"] + " [E01_2]"
    assert "original_source_chunk" not in evidence
    assert evidence["text_provenance"] == "reviewed_summary_translation_not_verbatim"
    await model.close()


def test_all_real_translations_preserve_canonical_ids_and_numeric_literals():
    source = json.loads((ROOT / "data/evidence.json").read_text(encoding="utf-8"))
    translated = json.loads((ROOT / "data/evidence.en.json").read_text(encoding="utf-8"))
    assert translated["source_corpus_sha256"] == corpus_hash(source)
    rows = {row["id"]: row["text"] for row in translated["items"]}
    assert set(rows) == {row["id"] for row in source}
    # Gene/cultivar/source identifiers contain digits but are not numeric values.
    # Clarifying an existing parameter's target must not look like a new value.
    def numeric_text(text):
        return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", "", text)
    for row in source:
        original = numeric_text(row["text"])
        english = numeric_text(rows[row["id"]])
        assert validate_numbers(english, [{"text": original}]), row["id"]
        assert validate_numbers(original, [{"text": english}]), row["id"]


@pytest.mark.asyncio
async def test_arbitrary_generated_answer_field_cannot_enter_english_product_response(tmp_path):
    from orchid.app import create_app
    settings, source, _ = fixture_data(tmp_path)
    key = tmp_path / "key"
    key.write_text("fixture-key")
    settings.key_file = str(key)

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
            "status": "answered", "answer": "Invented concentration is 0.99.",
            "selections": [{"source_id": "E01", "paragraph_index": 0}]})}}]})

    class Index:
        ready = True

        def search(self, question, history, language="zh-TW"):
            return source

    model = ModelClient(settings, httpx.MockTransport(handle), len)
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = (await client.post("/api/chat", json={"question": "test", "language": "en"})).json()
    assert result["status"] == "unknown" and result["citations"] == []
    assert "Invented" not in result["answer"] and "0.99" not in result["answer"]
    await model.close()
