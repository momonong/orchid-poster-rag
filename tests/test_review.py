import json
import sqlite3
from contextlib import closing
from uuid import uuid4

import httpx
import pytest

from orchid.app import create_app
from orchid.config import Settings
from orchid.records import RecordStore

TOKEN = "synthetic-review-token-" + "x" * 32
AUTH = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def review_app(tmp_path, monkeypatch):
    key = tmp_path / "review.key"
    key.write_text(TOKEN, encoding="utf-8")
    monkeypatch.setenv("ORCHID_REVIEW_KEY_FILE", str(key))
    settings = Settings(root=tmp_path)
    store = RecordStore(settings.records_file)
    store.initialize()
    for i in range(4):
        rid = str(uuid4())
        store.claim_question(request_id=rid, fingerprint=str(i), conversation_id=str(uuid4()),
            question=f"question {i} 100% <script>alert(1)</script>", language="en" if i % 2 else "zh-TW",
            section="clue1", history_hash="private", model_id="synthetic", corpus_hash="synthetic")
        store.complete_question(rid, {"status": "answered" if i % 2 else "unknown",
            "answer": f"reply {i}", "citations": [{"id": "P01"}]}, latency_ms=50)
    store.save_feedback(submission_id=str(uuid4()), fingerprint="feedback", conversation_id=str(uuid4()),
        language="zh-TW", section="overview", clarity="partly", comment="希望文字大一點")
    return create_app(settings), settings


@pytest.mark.asyncio
async def test_review_requires_separate_secret_and_never_returns_data_to_anonymous(review_app):
    app, _ = review_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": b"Bearer \xff"}):
            r = await c.get("/review/api/records", headers=headers)
            assert r.status_code == 401
            assert "question 0" not in r.text and "希望" not in r.text
        r = await c.get("/review/api/records", headers=AUTH)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_review_is_read_only_bounded_and_searches_literal_text(review_app):
    app, settings = review_app
    with closing(sqlite3.connect(settings.records_file)) as db:
        before = list(db.iterdump())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        r = (await c.get("/review/api/records?limit=2", headers=AUTH)).json()
        assert r["totals"] == {"questions": 4, "feedback": 1}
        assert r["total"] == 4 and len(r["items"]) == 2
        assert "fingerprint" not in json.dumps(r) and "history_hash" not in json.dumps(r)
        second = (await c.get("/review/api/records?limit=2&offset=2", headers=AUTH)).json()
        assert {x["id"] for x in r["items"]}.isdisjoint(x["id"] for x in second["items"])
        found = (await c.get("/review/api/records", params={"q": "100%", "language": "zh-TW",
            "status": "unknown"}, headers=AUTH)).json()
        assert found["total"] == 2 and found["items"][0]["answer"].startswith("reply")
        assert (await c.get("/review/api/records", params={"q": "' OR 1=1 --"}, headers=AUTH)).json()["total"] == 0
        feedback = (await c.get("/review/api/records?kind=feedback", headers=AUTH)).json()
        assert feedback["items"][0]["comment"] == "希望文字大一點"
        for query in ("limit=1000", "offset=-1", "kind=questions;DROP", "q=" + "a" * 201):
            assert (await c.get("/review/api/records?" + query, headers=AUTH)).status_code == 422
        assert (await c.post("/review/api/records", headers=AUTH)).status_code == 405
    with closing(sqlite3.connect(settings.records_file)) as db:
        assert list(db.iterdump()) == before


@pytest.mark.asyncio
async def test_review_disabled_without_key_and_missing_db_is_not_created(tmp_path, monkeypatch):
    monkeypatch.delenv("ORCHID_REVIEW_KEY_FILE", raising=False)
    settings = Settings(root=tmp_path)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        assert (await c.get("/review/api/records", headers=AUTH)).status_code == 503
    assert not settings.records_file.exists()
    key = tmp_path / "review.key"
    key.write_text(TOKEN)
    settings.review_key_file = str(key)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
        assert (await c.get("/review/api/records", headers=AUTH)).status_code == 503
    assert not settings.records_file.exists()


@pytest.mark.asyncio
async def test_review_shell_prefix_and_no_private_data(review_app):
    app, _ = review_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, root_path="/orchid-poster"),
            base_url="https://test/orchid-poster/") as c:
        r = await c.get("review")
        assert r.status_code == 200 and "審閱密碼" in r.text
        assert "question 0" not in r.text and TOKEN not in r.text
        assert "/orchid-poster/review/review.js" in r.text
        assert (await c.get("review/api/records", headers=AUTH)).json()["total"] == 4


@pytest.mark.asyncio
async def test_review_read_during_wal_writer_does_not_block_or_change_it(review_app):
    app, settings = review_app
    with closing(sqlite3.connect(settings.records_file)) as writer:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE questions SET question='uncommitted' WHERE rowid=1")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as c:
            r = await c.get("/review/api/records", headers=AUTH)
            assert r.status_code == 200 and r.json()["total"] == 4
            assert all(x["question"] != "uncommitted" for x in r.json()["items"])
        writer.rollback()
