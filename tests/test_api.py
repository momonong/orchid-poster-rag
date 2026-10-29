import asyncio
import importlib.util
import json

import httpx
import pytest

from orchid.config import QWEN_REVISION, Settings
from orchid.generation import ModelClient, UnknownResult


class FixtureIndex:
    ready, reason = True, "fixture index"
    def search(self, question, history, language="zh-TW"):
        return [{"id": "P01", "text": "G_A 增大只讓斑點變大。", "title": "fixture",
                 "document": "paper", "section": "Results", "kind": "模擬", "page": 4}]


class FixtureModel:
    info, reason, quarantined = {"id": "fixture"}, "fixture", False
    def __init__(self, answer):
        self.answer = answer
        self.calls = []
    async def probe(self):
        return True
    async def generate(self, question, history, passages, language="en"):
        self.calls.append((question, history))
        return {"status": "answered", "answer": self.answer}
    async def close(self):
        pass


@pytest.mark.asyncio
async def test_api_rejects_foreign_citation_and_separates_histories(tmp_path):
    assert importlib.util.find_spec("orchid.app") is not None, "API application must exist"
    from orchid.app import create_app
    model = FixtureModel("斑點變大 [P99]")
    app = create_app(Settings(root=tmp_path), FixtureIndex(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/chat", json={"question": "第一位訪客"})
        assert first.json()["status"] == "unknown"
        assert first.json()["citations"] == []
        model.answer = "在這些條件下只讓斑點變大 [P01]"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://visitor-two") as second_client:
            second = await second_client.post("/api/chat", json={"question": "另一位訪客"})
            assert second.json()["status"] == "answered"
        assert model.calls[1][1] == []
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://visitor-three") as third:
            third_history = [{"role": "user", "content": "第三位訪客自己的前文"}]
            response = await third.post("/api/chat", json={"question": "第三位追問", "history": third_history})
            assert response.json()["status"] == "answered"
            assert model.calls[2][1] == third_history
            assert "第一位訪客" not in str(model.calls[2][1])
        model.answer = "數值是 0.02 [P01]"
        numeric = await client.post("/api/chat", json={"question": "數字"})
        assert numeric.json()["status"] == "unknown"
        model.answer = "只有提高 G_A 才能形成融合斑塊 [P01]"
        overclaim = await client.post("/api/chat", json={"question": "融合條件"})
        assert overclaim.json()["status"] == "unknown"
        assert overclaim.json()["citations"] == []
        assert (await client.post("/api/chat", json={"question": "x" * 601})).status_code == 422
        assert (await client.post("/api/chat", content="x" * 17000,
                                   headers={"content-type": "application/json"})).status_code == 413


@pytest.mark.asyncio
async def test_model_uses_ready_and_actual_id_without_unsupported_parameters(tmp_path):
    key = tmp_path / "key"
    key.write_text("fixture-secret")
    calls = []
    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True, "inflight": 0, "detached": 0, "uncertain": 0})
        assert request.headers["authorization"] == "Bearer fixture-secret"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B",
                "capabilities": {"text": True}, "revision": QWEN_REVISION, "backend": "transformers",
                "max_model_len": 8192}]})
        payload = json.loads(request.content)
        assert "response_format" not in payload
        assert payload["temperature"] == 0 and payload["top_p"] == 1
        assert payload["chat_template_kwargs"] == {"enable_thinking": False}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": '{"status":"answered","answer":"fixture [P01]"}'}}]})
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    result = await model.generate("測試", [], [{"id": "P01", "text": "fixture", "kind": "test", "section": "test"}], "zh-TW")
    assert result["answer"] == "fixture [P01]"
    assert calls == ["/health/ready", "/v1/models", "/v1/chat/completions"]
    await model.close()


@pytest.mark.asyncio
async def test_bounded_queue_rejects_fourth_request():
    from orchid.generation import Busy, GenerationQueue
    queue = GenerationQueue(max_pending=2, wait_seconds=0.1)
    release = asyncio.Event()
    first = asyncio.create_task(queue.run(release.wait))
    await asyncio.sleep(0.01)
    second = asyncio.create_task(queue.run(release.wait))
    third = asyncio.create_task(queue.run(release.wait))
    await asyncio.sleep(0.01)
    with pytest.raises(Busy):
        await queue.run(release.wait)
    release.set()
    await asyncio.gather(first, second, third)


@pytest.mark.asyncio
async def test_completed_format_error_is_not_presented_as_timeout(tmp_path):
    from orchid.app import create_app
    class FormatFailureModel(FixtureModel):
        async def generate(self, question, history, passages, language="en"):
            raise UnknownResult("模型回覆未完整或格式不符，未顯示未驗證內容")
    app = create_app(Settings(root=tmp_path), FixtureIndex(), FormatFailureModel(""))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "格式問題", "language": "zh-TW"})
    body = response.json()
    assert body["status"] == "unknown"
    assert "格式不符" in body["answer"]
    assert "逾時" not in body["answer"]
    assert "仍可能在處理" not in body["answer"]


@pytest.mark.asyncio
async def test_inhibitor_self_activation_is_not_returned_as_an_answer(tmp_path):
    from orchid.app import create_app
    model = FixtureModel("PeMYBx 作為抑制者 H 透過 G_H 活化自身並抑制 A 的合成 [P01]。")
    app = create_app(Settings(root=tmp_path), FixtureIndex(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "如何產生斑點？", "language": "zh-TW"})
    body = response.json()
    assert body["status"] == "unknown" and body["citations"] == []
    assert "活化自身" not in body["answer"]
