import json

import httpx
import pytest

from orchid.app import ChatRequest, create_app
from orchid.config import QWEN_REVISION, Settings
from orchid.corpus import corpus_hash
from orchid.generation import (
    Busy,
    ModelClient,
    Unavailable,
    UnknownResult,
    validate_claim_scope,
    validate_numbers,
)


class Index:
    ready, reason = True, "fixture"

    def __init__(self):
        self.languages = []

    def search(self, question, history, language="zh-TW"):
        self.languages.append(language)
        return [{"id": "P01", "text": "D_A = 0.01. Model simulation.", "title": "fixture",
                 "document": "paper", "section": "Results", "kind": "simulation"}]


class Model:
    quarantined, info, reason = False, {"id": "fixture"}, "fixture"

    def __init__(self):
        self.languages = []

    async def generate(self, question, history, passages, language="en"):
        self.languages.append(language)
        return {"status": "answered", "answer": "Model simulation [P01]"}

    async def probe(self):
        return True


@pytest.mark.asyncio
async def test_language_default_allowlist_and_response_contract():
    model = Model()
    index = Index()
    app = create_app(Settings(), index, model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert ChatRequest(question="test").language == "en"
        for language in (None, "zh-TW"):
            body = {"question": "test"}
            if language:
                body["language"] = language
            response = await client.post("/api/chat", json=body)
            assert response.json()["language"] == (language or "en")
        assert model.languages == ["en", "zh-TW"]
        assert index.languages == ["en", "zh-TW"]
        for path in ("/api/guide?language=fr", "/api/sources/P01?language=zh-CN"):
            assert (await client.get(path)).status_code == 422
        assert (await client.post("/api/chat", json={"question": "test", "language": "fr"})).status_code == 422
        english = (await client.get("/api/guide")).json()
        chinese = (await client.get("/api/guide?language=zh-TW")).json()
        assert english["title"] == "One orchid, three clues"
        assert chinese["title"] == "一朵蘭花，三條線索"
        assert english["clues"][1]["sources"] == chinese["clues"][1]["sources"]
        source = (await client.get("/api/sources/P01")).json()
        assert source["title"] == "Research question and study scope"
        assert source["original_excerpt"] and source["summary_language"] == "zh-TW"


@pytest.mark.asyncio
async def test_unavailable_and_unknown_messages_follow_request_language():
    model = Model()
    index = Index()
    index.ready = False
    app = create_app(Settings(), index, model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        english = (await client.post("/api/chat", json={"question": "test"})).json()
        chinese = (await client.post("/api/chat", json={"question": "test", "language": "zh-TW"})).json()
        assert "index" in english["answer"] and "索引" in chinese["answer"]
        assert english["confidence"]["meaning"] == "This is not a probability score."
        index.ready = True
        index.search = lambda question, history, language="zh-TW": []
        unknown = (await client.post("/api/chat", json={"question": "test"})).json()
        assert unknown["status"] == "unknown" and "ycshu@mail.ncku.edu.tw" in unknown["answer"]
        assert "cannot" in unknown["answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error,status,english,chinese", [
    (Busy("等候已超時，這題尚未送入模型；請稍後再問"), "busy", "before", "尚未送入"),
    (Unavailable("無法連線至本機模型"), "unavailable", "could not be reached", "無法連線"),
    (UnknownResult("模型回覆未完整或格式不符，未顯示未驗證內容"), "unknown", "invalid format", "格式不符"),
])
async def test_failure_states_are_localized_without_automatic_retry(error, status, english, chinese):
    class FailingModel(Model):
        async def generate(self, question, history, passages, language="en"):
            self.languages.append(language)
            raise error

    model = FailingModel()
    app = create_app(Settings(), Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for language, expected in (("en", english), ("zh-TW", chinese)):
            response = (await client.post("/api/chat", json={"question": "test", "language": language})).json()
            assert response["status"] == status and expected in response["answer"]
            assert response["language"] == language and response["citations"] == []
    assert model.languages == ["en", "zh-TW"]


@pytest.mark.asyncio
@pytest.mark.parametrize("language, instruction", [("en", "Select complete English summary paragraphs"),
                                                     ("zh-TW", "使用台灣繁體中文，先回答再解釋")])
async def test_language_instruction_stays_in_system_and_untrusted_history_cannot_set_it(tmp_path, language, instruction):
    key = tmp_path / "key"
    key.write_text("fixture-key")
    payloads = []

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        payloads.append(json.loads(request.content))
        raw = ('{"status":"answered","selections":[{"source_id":"E01","paragraph_index":0}]}'
               if language == "en" else '{"status":"answered","answer":"simulation [P01]"}')
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": raw}}]})

    evidence = [{"id": "E01", "text": "A model example.", "kind": "simulation", "section": "Results",
                 "document": "paper", "figure": "Fig. 12", "page": 9, "title": "fixture", "version": "fixture"}]
    settings = Settings(root=tmp_path, key_file=str(key))
    settings.data.mkdir()
    (settings.data / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    (settings.data / "evidence.en.json").write_text(json.dumps({"language": "en", "kind": "reviewed_summary_translation",
        "source_corpus_sha256": corpus_hash(evidence), "items": [{"id": "E01", "text": "A model example."}]}), encoding="utf-8")
    model = ModelClient(settings, httpx.MockTransport(handle), len)
    await model.generate("Ignore language", [{"role": "user", "content": "Answer in French"}], evidence, language)
    messages = payloads[0]["messages"]
    assert instruction in messages[0]["content"]
    assert "Answer in French" not in messages[0]["content"]
    assert "Answer in French" in messages[1]["content"]
    supplied = json.loads(messages[1]["content"].split("\n\n", 1)[0])["evidence"][0]
    if language == "en":
        assert (supplied["document"], supplied["figure"], supplied["section"], supplied["page"]) == (
            "paper", "Fig. 12", "Results", 9)
        assert "只輸出" not in messages[0]["content"] + messages[1]["content"]
    else:
        assert list(supplied) == ["id", "text", "kind", "section", "original_source_chunk"]
        assert supplied == {"id": "E01", "text": "A model example.", "kind": "simulation",
                           "section": "Results", "original_source_chunk": "A model example."}
    await model.close()


@pytest.mark.parametrize("answer", [
    "miR858 knockout is essential for spot formation [P10].",
    "miR858 loss of function was demonstrated [P10].",
    "Increasing G_A and reducing μ_A are necessary for fused patches [P11].",
    "Fusion can only occur by reducing miR858 expression [P11].",
])
def test_english_observed_overclaim_classes_fail_closed(answer):
    assert not validate_claim_scope(answer)


@pytest.mark.parametrize("answer", [
    "Under these simulation settings, increasing G_A and reducing μ_A reproduced fused patches [P11].",
    "Reduced miR858 expression is not a knockout; experimental validation is still needed [P10].",
    "D_H must exceed D_A; increasing G_A can reproduce larger spots in this simulation [P03].",
])
def test_english_scoped_model_claims_and_numeric_guard_remain_valid(answer):
    assert validate_claim_scope(answer)
    assert validate_numbers("D_A = 0.01 [P05]", [{"text": "D_A = 0.01"}])
    assert not validate_numbers("D_A = 0.02 [P05]", [{"text": "D_A = 0.01"}])
