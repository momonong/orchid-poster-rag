import json

import httpx
import pytest

from orchid.config import QWEN_REVISION, Settings
from orchid.generation import ModelClient, Unavailable, UnknownResult, validate_answer


def test_rejects_malformed_and_unrelated_bracket_citations():
    assert not validate_answer("有引用 [P01]，但又編造了 [FAKE]", {"P01"})
    assert not validate_answer("有引用 [P01]，但又編造了 [P99]", {"P01"})


@pytest.mark.asyncio
async def test_unknown_transport_is_quarantined_until_finite_idle_probe(tmp_path):
    key = tmp_path / "key"
    key.write_text("test-key")
    state = {"ready": True, "inflight": 0, "detached": 0, "uncertain": 0}
    posts = []
    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json=state)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION, "max_model_len": 8192,
                                                     "capabilities": {"text": True}}]})
        posts.append(json.loads(request.content))
        state["inflight"] = 1
        raise httpx.ReadTimeout("fixture transport timed out")
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    with pytest.raises(UnknownResult):
        await model.generate("fixture", [], [], "zh-TW")
    assert model.quarantined
    assert not await model.probe()
    assert len(posts) == 1
    state["inflight"] = 0
    assert await model.probe()
    assert not model.quarantined
    await model.close()


@pytest.mark.asyncio
async def test_undeclared_context_is_not_assumed(tmp_path):
    key = tmp_path / "key"
    key.write_text("test-key")
    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "capabilities": {"text": True}}]})
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    assert not await model.probe()
    assert "CONTEXT" in model.reason
    with pytest.raises(Unavailable):
        await model.generate("fixture", [], [], "zh-TW")
    await model.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [[], None, {"status": "answered", "answer": []}])
async def test_nonobject_generation_output_fails_closed(tmp_path, output):
    key = tmp_path / "key"
    key.write_text("test-key")
    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(output)}}]})
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    with pytest.raises(UnknownResult):
        await model.generate("fixture", [], [], "zh-TW")
    await model.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [
    '{"answer":"a [P01]"}',
    '{"status":"answered","answer":"a [P01]","answer":"b [P01]"}',
    '{"status":"unknown","status":"answered","answer":"a [P01]"}',
])
async def test_duplicate_json_keys_and_missing_status_never_count_as_success(tmp_path, raw):
    key = tmp_path / "key"
    key.write_text("test-key")
    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": raw}}]})
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    with pytest.raises(UnknownResult):
        await model.generate("fixture", [], [], "zh-TW")
    await model.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [[], None, {"error": "Bad Gateway"}])
async def test_malformed_gateway_error_always_quarantines(tmp_path, output):
    key = tmp_path / "key"
    key.write_text("test-key")
    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"ready": True})
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-4B", "revision": QWEN_REVISION,
                "max_model_len": 8192, "capabilities": {"text": True}}]})
        return httpx.Response(502, content=json.dumps(output), headers={"Content-Type": "application/json"})
    model = ModelClient(Settings(root=tmp_path, key_file=str(key)), httpx.MockTransport(handle), len)
    with pytest.raises(UnknownResult):
        await model.generate("fixture", [], [], "zh-TW")
    assert model.quarantined
    await model.close()
