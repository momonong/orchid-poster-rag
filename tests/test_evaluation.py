import json

import httpx
import pytest

from orchid import evaluation

READY = {"app": "ready", "index": {"ready": True}, "model": {"ready": True},
         "queue": {"active": 0, "pending": 0}}


def case(name):
    return {"id": name, "question": name, "answerable": True, "source_any": ["P01"],
            "key_points": [], "forbidden": []}


@pytest.mark.asyncio
async def test_live_evaluation_records_product_validated_response():
    assert callable(getattr(evaluation, "run_live", None)), "live evaluation must use the product API"
    product = {"status": "unknown", "answer": "產品驗證後的證據不足回覆", "citations": [],
               "poster_sections": [], "confidence": {"level": "insufficient"}}
    posts = []
    def handle(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json=READY)
        assert request.url.path == "/api/chat"
        posts.append(json.loads(request.content))
        return httpx.Response(200, json=product)
    snapshots, report = [], {"results": []}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle)) as client:
        await evaluation.run_live([case("one")], client, report,
                                  lambda: snapshots.append(json.loads(json.dumps(report))))
    assert posts == [{"question": "one", "history": [], "language": "zh-TW"}]
    assert report["results"][0]["language"] == "zh-TW"
    assert report["results"][0]["product_response"] == product
    assert report["results"][0]["status"] == "unknown"
    assert report["state"] == "complete"
    assert snapshots[-1]["results"][0]["product_response"] == product


@pytest.mark.asyncio
async def test_live_evaluation_can_explicitly_request_english():
    posts = []
    def handle(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json=READY)
        posts.append(json.loads(request.content))
        return httpx.Response(200, json={"status": "answered", "answer": "A simulation [P01]"})
    report = {"results": []}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle)) as client:
        await evaluation.run_live([case("one")], client, report, lambda: None, language="en")
    assert posts == [{"question": "one", "history": [], "language": "en"}]
    assert report["results"][0]["language"] == "en"


@pytest.mark.asyncio
async def test_live_timeout_preserves_prior_checkpoint_and_never_retries():
    assert callable(getattr(evaluation, "run_live", None)), "live evaluation needs per-question checkpoints"
    posts, snapshots, report = [], [], {"results": []}
    def handle(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json=READY)
        question = json.loads(request.content)["question"]
        posts.append(question)
        if question == "two":
            raise httpx.ReadTimeout("fixture timeout")
        return httpx.Response(200, json={"status": "answered", "answer": "產品回覆 [P01]",
                                       "citations": [{"id": "P01"}], "confidence": {"level": "citation_validated"}})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle)) as client:
        await evaluation.run_live([case("one"), case("two"), case("three")], client, report,
                                  lambda: snapshots.append(json.loads(json.dumps(report))))
    assert posts == ["one", "two"]
    assert report["state"] == "stopped"
    assert report["results"][0]["status"] == "answered"
    assert report["results"][1]["status"] == "unknown"
    assert any(s["results"] and s["results"][0].get("product_response") for s in snapshots)
    assert report["results"][1]["error"] == "transport_result_unknown"


@pytest.mark.asyncio
async def test_live_unavailable_preflight_checkpoints_without_generation():
    assert callable(getattr(evaluation, "run_live", None)), "unavailable live runs must save their state"
    requests, snapshots, report = [], [], {"results": []}
    def handle(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={**READY, "model": {"ready": False}})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle)) as client:
        await evaluation.run_live([case("one")], client, report,
                                  lambda: snapshots.append(json.loads(json.dumps(report))))
    assert requests == ["/api/health"]
    assert report["state"] == "blocked"
    assert snapshots[-1]["results"] == []
