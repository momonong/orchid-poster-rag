import asyncio
import csv
import importlib.util
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from orchid.app import create_app
from orchid.config import Settings


class Index:
    ready, reason = True, "synthetic index"

    def search(self, question, history, language="en"):
        return [{"id": "P01", "text": "Patterns vary.", "title": "Synthetic evidence",
                 "document": "paper", "section": "Results", "kind": "simulation", "page": 1,
                 "poster_sections": ["clue1"]}]


class Model:
    info, reason, quarantined = {"id": "synthetic-model"}, "synthetic", False

    def __init__(self, release=None, answer=None):
        self.calls = []
        self.started = asyncio.Event()
        self.release = release
        self.answer = answer

    async def probe(self):
        return True

    async def generate(self, question, history, passages, language="en"):
        self.calls.append((question, history, language))
        self.started.set()
        if self.release:
            await self.release.wait()
        return {"status": "answered", "answer": self.answer or question + " [P01]"}

    async def close(self):
        pass


def rows(settings, table="questions"):
    with sqlite3.connect(settings.records_file) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM " + table)]


def new_store(path, **kwargs):
    assert importlib.util.find_spec("orchid.records") is not None, "SQLite records store must exist"
    from orchid.records import RecordStore
    return RecordStore(path, **kwargs)


def claim(store, request_id=None, question="synthetic question", fingerprint="same", **kwargs):
    return store.claim_question(request_id=request_id or str(uuid4()), fingerprint=fingerprint,
        question=question, language="en", section="clue1", conversation_id=str(uuid4()),
        history_hash="hash-only", model_id="synthetic", corpus_hash="synthetic-corpus", **kwargs)


@pytest.mark.asyncio
async def test_chat_saves_only_validated_visitor_reply_and_replays_without_generation(tmp_path):
    settings = Settings(root=tmp_path)
    settings.index.mkdir(parents=True)
    (settings.index / "manifest.json").write_text(json.dumps({"corpus_hash": "synthetic-index-corpus-version"}))
    model = Model(answer="Unvalidated raw answer [P99]")
    app = create_app(settings, Index(), model)
    request_id = str(uuid4())
    payload = {"request_id": request_id, "question": "  visitor question  ", "section": "clue1",
               "history": [{"role": "user", "content": "private history not persisted"}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json=payload)
        assert response.status_code == 200
        receipt = response.json()
        assert receipt.get("record_saved") is True
        assert receipt["request_id"] == request_id and receipt["status"] == "unknown"
        replay = await client.post("/api/chat", json=payload)
        assert replay.json() == receipt and len(model.calls) == 1
        conflict = await client.post("/api/chat", json={**payload, "question": "different"})
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "request_conflict"
    saved = rows(settings)[0]
    assert saved["question"] == "  visitor question  "
    assert saved["corpus_hash"] == "synthetic-index-corpus-version"
    assert saved["status"] == "unknown" and saved["state"] == "completed"
    assert json.loads(saved["response_json"]) == receipt
    assert "Unvalidated raw answer" not in json.dumps(saved)
    assert "private history not persisted" not in json.dumps(saved)


@pytest.mark.asyncio
async def test_pending_duplicate_does_not_dispatch_and_cancelled_client_still_completes(tmp_path):
    settings = Settings(root=tmp_path)
    release = asyncio.Event()
    model = Model(release)
    app = create_app(settings, Index(), model)
    payload = {"question": "cancelled visitor", "request_id": str(uuid4()), "conversation_id": str(uuid4())}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/chat", json=payload))
        await asyncio.wait_for(model.started.wait(), 3)
        duplicate = await client.post("/api/chat", json=payload)
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "request_in_progress"
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        release.set()
        for _ in range(100):
            if rows(settings)[0]["state"] == "completed":
                break
            await asyncio.sleep(.01)
        assert rows(settings)[0]["state"] == "completed"
        replay = await client.post("/api/chat", json=payload)
        assert replay.json()["record_saved"] is True and len(model.calls) == 1


@pytest.mark.asyncio
async def test_feedback_validates_preserves_original_and_is_idempotent(tmp_path):
    settings = Settings(root=tmp_path)
    app = create_app(settings, Index(), Model())
    payload = {"submission_id": str(uuid4()), "conversation_id": None, "language": "zh-TW",
               "section": "supplementary", "clarity": "partly", "comment": "  原文 =保留\n"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/feedback", json=payload)
        assert first.status_code == 201
        again = await client.post("/api/feedback", json=payload)
        assert again.status_code == 201 and again.json() == first.json()
        conflict = await client.post("/api/feedback", json={**payload, "comment": "different"})
        assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "request_conflict"
        for changes in [{"comment": " ", "clarity": None}, {"extra": "forbidden"}, {"comment": "x"*1501},
                        {"section": "other"}, {"submission_id": "invalid"}, {"clarity": "good"}]:
            assert (await client.post("/api/feedback", json={**payload, **changes})).status_code == 422
        for changes in [{"request_id": "bad"}, {"conversation_id": "bad"}, {"section": "other"}, {"extra": True}]:
            assert (await client.post("/api/chat", json={"question": "valid", **changes})).status_code == 422
    assert rows(settings, "feedback")[0]["comment"] == payload["comment"]


@pytest.mark.asyncio
async def test_recording_failure_prevents_model_and_never_exposes_path(tmp_path, monkeypatch):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("fixture")
    monkeypatch.setenv("ORCHID_RECORDS_FILE", str(blocked / "private-database.sqlite3"))
    model = Model()
    app = create_app(Settings(root=tmp_path), Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "synthetic"})
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "recording_unavailable"
        assert model.calls == [] and "private-database" not in response.text
        health = await client.get("/api/health")
        assert health.json()["recording"]["ready"] is False
        assert str(blocked) not in health.text
        assert (await client.post("/api/feedback", json={"submission_id": str(uuid4()),
            "language": "en", "section": "overview", "comment": "hello"})).status_code == 503


@pytest.mark.asyncio
async def test_parallel_questions_feedback_do_not_mix_histories_or_records(tmp_path):
    settings = Settings(root=tmp_path)
    model = Model()
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        async def submit(word):
            chat = await client.post("/api/chat", json={"question": word, "conversation_id": str(uuid4()),
                "history": [{"role": "user", "content": "history-"+word}]})
            feedback = await client.post("/api/feedback", json={"submission_id": str(uuid4()),
                "language": "en", "section": "overview", "comment": word})
            return chat, feedback
        replies = await asyncio.gather(*(submit(w) for w in ["alpha", "beta", "gamma"]))
    assert all(c.status_code == 200 and c.json()["record_saved"] for c, _ in replies)
    assert all(f.status_code == 201 for _, f in replies)
    assert {r["question"] for r in rows(settings)} == {"alpha", "beta", "gamma"}
    for r in rows(settings):
        assert json.loads(r["response_json"])["answer"] == r["question"] + " [P01]"
    assert all(history == [{"role": "user", "content": "history-"+question}] for question, history, _ in model.calls)
    assert {r["comment"] for r in rows(settings, "feedback")} == {"alpha", "beta", "gamma"}


def test_store_parallel_persistence_and_restart_marks_only_pending(tmp_path):
    path = tmp_path / "real.sqlite3"
    store = new_store(path)
    store.initialize()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: claim(store, question=str(i)), range(16)))
    reopened = new_store(path, recover_pending=True)
    reopened.initialize()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions WHERE state='interrupted' AND response_json IS NULL").fetchone()[0] == 16
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_busy_timeout_is_bounded_and_failed_transaction_leaves_no_record(tmp_path):
    from orchid.records import RecordingUnavailable
    path = tmp_path / "locked.sqlite3"
    store = new_store(path, busy_timeout_ms=75)
    store.initialize()
    with sqlite3.connect(path, isolation_level=None) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        start = time.monotonic()
        with pytest.raises(RecordingUnavailable):
            claim(store)
        assert time.monotonic()-start < .75
        blocker.rollback()
    claim(store)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1


def test_export_csv_formula_safety_raw_snapshot_and_no_overwrite(tmp_path):
    from orchid.records import export_records
    database = tmp_path / "source.sqlite3"
    store = new_store(database)
    rid = str(uuid4())
    claim(store, request_id=rid, question="  =SUM(A1:A2)")
    response = {"status": "unknown", "answer": "原文\nsecond line", "citations": [], "poster_sections": []}
    store.complete_question(rid, response, latency_ms=17, model_id="synthetic")
    store.save_feedback(submission_id=str(uuid4()), fingerprint="f", conversation_id=None,
        language="en", section="intro", clarity=None, comment="\t@formula")
    out = tmp_path / "export"
    export_records(database, out)
    assert (out / "questions.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    with (out / "questions.csv").open(encoding="utf-8-sig", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["question"] == "'  =SUM(A1:A2)" and row["answer"] == "原文\nsecond line"
    with (out / "feedback.csv").open(encoding="utf-8-sig", newline="") as f:
        assert next(csv.DictReader(f))["comment"] == "'\t@formula"
    with sqlite3.connect(out / "records.sqlite3") as db:
        assert db.execute("SELECT question FROM questions").fetchone()[0] == "  =SUM(A1:A2)"
    with pytest.raises(FileExistsError):
        export_records(database, out)
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises((ValueError, FileNotFoundError)):
        export_records(missing, tmp_path / "missing-export")
    assert not missing.exists()


@pytest.mark.asyncio
async def test_record_database_and_export_routes_are_not_public(tmp_path, monkeypatch):
    settings = Settings(root=tmp_path)
    db = tmp_path / ".orchid" / "assets" / "private.sqlite3"
    monkeypatch.setenv("ORCHID_RECORDS_FILE", str(db))
    app = create_app(settings, Index(), Model())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/chat", json={"question": "fixture"})).status_code == 200
        for url in ["/api/records", "/api/feedback", "/api/records/export", "/assets/private.sqlite3",
                    "/assets/private.sqlite3-wal", "/assets/private.sqlite3-shm", "/.orchid/visitor-records.sqlite3"]:
            assert (await client.get(url)).status_code in {404, 405}


def test_cli_export_uses_explicit_local_database(tmp_path, monkeypatch, capsys):
    from orchid.cli import main
    database = tmp_path / "cli.sqlite3"
    new_store(database).initialize()
    out = tmp_path / "cli-export"
    monkeypatch.setattr("sys.argv", ["orchid", "export-records", "--database", str(database), "--output", str(out)])
    main()
    assert (out / "questions.csv").is_file() and (out / "feedback.csv").is_file()
    assert "fixture-secret" not in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("busy", "busy"), ("unavailable", "unavailable"), ("unknown", "unknown")])
async def test_failure_receipts_are_persisted_and_replayed(tmp_path, failure, status):
    from orchid.generation import Busy, Unavailable, UnknownResult

    class FailureModel(Model):
        async def generate(self, question, history, passages, language="en"):
            self.calls.append(question)
            raise {"busy": Busy, "unavailable": Unavailable, "unknown": UnknownResult}[failure]("synthetic failure")

    model = FailureModel()
    settings = Settings(root=tmp_path)
    app = create_app(settings, Index(), model)
    body = {"question": "synthetic question", "request_id": str(uuid4())}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/chat", json=body)
        second = await client.post("/api/chat", json=body)
    assert first.json()["status"] == status and first.json()["record_saved"] is True
    assert second.json() == first.json() and len(model.calls) == 1
    assert rows(settings)[0]["status"] == status


@pytest.mark.asyncio
async def test_all_fingerprint_fields_prevent_accidental_reuse(tmp_path):
    model = Model()
    app = create_app(Settings(root=tmp_path), Index(), model)
    body = {"request_id": str(uuid4()), "conversation_id": str(uuid4()), "question": "alpha",
            "language": "en", "section": "intro", "history": []}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/chat", json=body)).json()["record_saved"] is True
        for change in [{"question": "beta"}, {"language": "zh-TW"}, {"section": "clue1"},
                       {"conversation_id": str(uuid4())}, {"history": [{"role": "user", "content": "changed"}]}]:
            response = await client.post("/api/chat", json={**body, **change})
            assert response.status_code == 409 and response.json()["detail"]["code"] == "request_conflict"
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_storage_lock_after_generation_never_claims_reply_was_saved(tmp_path):
    release = asyncio.Event()
    settings = Settings(root=tmp_path)
    model = Model(release)
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        pending = asyncio.create_task(client.post("/api/chat", json={"question": "alpha"}))
        await asyncio.wait_for(model.started.wait(), 3)
        with sqlite3.connect(settings.records_file, isolation_level=None) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            release.set()
            response = await pending
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "recording_unavailable"
            assert "record_saved" not in response.text
            blocker.rollback()
    assert rows(settings)[0]["state"] == "pending" and rows(settings)[0]["response_json"] is None


@pytest.mark.asyncio
async def test_restart_does_not_replay_an_interrupted_question(tmp_path):
    from uuid import NAMESPACE_URL, uuid5

    from orchid.records import payload_hash
    settings = Settings(root=tmp_path)
    request_id = str(uuid4())
    conversation_id = str(uuid5(NAMESPACE_URL, request_id))
    fingerprint = payload_hash({"question": "alpha", "language": "en", "section": "overview",
                                "history_hash": payload_hash([]), "conversation_id": conversation_id})
    store = new_store(settings.records_file)
    store.claim_question(request_id=request_id, fingerprint=fingerprint, question="alpha", language="en",
        section="overview", conversation_id=conversation_id, history_hash="hash", model_id="synthetic", corpus_hash=None)
    model = Model()
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "alpha", "request_id": request_id})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "request_interrupted"
    assert model.calls == []
    assert rows(settings)[0]["state"] == "interrupted" and rows(settings)[0]["response_json"] is None


@pytest.mark.asyncio
async def test_disconnected_queued_question_is_not_discarded(tmp_path):
    release = asyncio.Event()
    model = Model(release)
    settings = Settings(root=tmp_path)
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        active = asyncio.create_task(client.post("/api/chat", json={"question": "alpha"}))
        await asyncio.wait_for(model.started.wait(), 3)
        waiting = asyncio.create_task(client.post("/api/chat", json={"question": "beta"}))
        for _ in range(100):
            if len(rows(settings)) == 2:
                break
            await asyncio.sleep(.01)
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)
        release.set()
        await active
        for _ in range(100):
            if all(r["state"] == "completed" for r in rows(settings)):
                break
            await asyncio.sleep(.01)
    assert len(model.calls) == 2
    assert len(rows(settings)) == 2 and all(r["state"] == "completed" for r in rows(settings))


def test_live_wal_backup_preserves_raw_feedback_and_all_csv_prefixes(tmp_path):
    from orchid.records import export_records
    database = tmp_path / "hot.sqlite3"
    store = new_store(database)
    store.initialize()
    comments = ["=1", "+1", "-1", "@cmd", "\ttext", "\rtext", "\ntext", "  =1", "ordinary 原文"]
    with sqlite3.connect(database) as keeper:
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("SELECT COUNT(*) FROM feedback").fetchone()  # Enter WAL before the short-lived writers.
        for comment in comments:
            store.save_feedback(submission_id=str(uuid4()), fingerprint=comment, conversation_id=None,
                                language="en", section="overview", clarity=None, comment=comment)
        assert Path(str(database)+"-wal").stat().st_size > 0
        export_records(database, tmp_path / "hot-export")
    with (tmp_path / "hot-export/feedback.csv").open(encoding="utf-8-sig", newline="") as f:
        exported = list(csv.DictReader(f))
    assert [r["comment"] for r in exported] == ["'"+s for s in comments[:-1]] + [comments[-1]]
    with sqlite3.connect(tmp_path / "hot-export/records.sqlite3") as snapshot:
        assert [r[0] for r in snapshot.execute("SELECT comment FROM feedback ORDER BY rowid")] == comments


@pytest.mark.asyncio
async def test_unknown_schema_is_not_modified_or_used_for_generation(tmp_path):
    settings = Settings(root=tmp_path)
    with sqlite3.connect(settings.records_file) as db:
        db.execute("PRAGMA user_version=99")
    model = Model()
    app = create_app(settings, Index(), model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "alpha"})
        assert response.status_code == 503 and model.calls == []
        assert (await client.get("/api/health")).json()["recording"]["ready"] is False
    with sqlite3.connect(settings.records_file) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99
