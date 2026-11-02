"""Local SQLite visitor receipts; no network access or raw history storage."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1


class RecordingUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("Visitor recording is unavailable.")


class RecordConflict(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def payload_hash(value):
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class RecordStore:
    def __init__(self, path, *, busy_timeout_ms=1000, recover_pending=False):
        self.path = Path(path)
        if not 1 <= busy_timeout_ms <= 5000:
            raise ValueError("Recording timeout must be between 1 and 5000 ms.")
        self.busy_timeout_ms = busy_timeout_ms
        self.recover_pending = recover_pending
        self._initialized = False
        self._initialization_lock = threading.Lock()

    def _open(self):
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        return connection

    def initialize(self):
        with self._initialization_lock:
            if self._initialized:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(self._open()) as db:
                    if db.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                        raise RecordingUnavailable()
                    db.execute("BEGIN IMMEDIATE")
                    try:
                        version = db.execute("PRAGMA user_version").fetchone()[0]
                        if version not in (0, SCHEMA_VERSION):
                            raise RecordingUnavailable()
                        if version == 0:
                            db.execute("""CREATE TABLE questions (
                                request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                                conversation_id TEXT, question TEXT NOT NULL, language TEXT NOT NULL,
                                section TEXT, history_hash TEXT NOT NULL, model_id TEXT, corpus_hash TEXT,
                                created_at TEXT NOT NULL, completed_at TEXT, latency_ms INTEGER,
                                state TEXT NOT NULL, status TEXT NOT NULL, response_json TEXT
                            )""")
                            db.execute("""CREATE TABLE feedback (
                                submission_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                                conversation_id TEXT, language TEXT NOT NULL, section TEXT NOT NULL,
                                clarity TEXT, comment TEXT NOT NULL, created_at TEXT NOT NULL
                            )""")
                            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                        if self.recover_pending:
                            db.execute("""UPDATE questions SET state='interrupted', status='interrupted',
                                completed_at=? WHERE state='pending'""", (utc_now(),))
                        db.commit()
                    except BaseException:
                        db.rollback()
                        raise
                self._initialized = True
            except (OSError, sqlite3.Error) as exc:
                raise RecordingUnavailable() from exc

    @contextmanager
    def _transaction(self):
        self.initialize()
        try:
            with closing(self._open()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    yield db
                    db.commit()
                except BaseException:
                    db.rollback()
                    raise
        except (OSError, sqlite3.Error) as exc:
            raise RecordingUnavailable() from exc

    def ready(self):
        try:
            # Verify write admission, without adding visitor data or exposing a path.
            with self._transaction():
                pass
            return True
        except RecordingUnavailable:
            return False

    def claim_question(self, *, request_id, fingerprint, conversation_id, question, language,
                       section, history_hash, model_id, corpus_hash):
        with self._transaction() as db:
            old = db.execute("SELECT fingerprint,state,response_json FROM questions WHERE request_id=?",
                             (request_id,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise RecordConflict("request_conflict")
                if old["state"] == "completed":
                    try:
                        return json.loads(old["response_json"])
                    except (ValueError, TypeError) as exc:
                        raise RecordingUnavailable() from exc
                raise RecordConflict("request_interrupted" if old["state"] == "interrupted"
                                     else "request_in_progress")
            db.execute("""INSERT INTO questions
                (request_id,fingerprint,conversation_id,question,language,section,history_hash,
                 model_id,corpus_hash,created_at,state,status)
                VALUES (?,?,?,?,?,?,?,?,?,?,'pending','pending')""",
                (request_id, fingerprint, conversation_id, question, language, section,
                 history_hash, model_id, corpus_hash, utc_now()))
        return None

    def complete_question(self, request_id, response, *, latency_ms, model_id=None):
        encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        with self._transaction() as db:
            changed = db.execute("""UPDATE questions SET state='completed',status=?,response_json=?,
                completed_at=?,latency_ms=?,model_id=COALESCE(?,model_id)
                WHERE request_id=? AND state='pending'""",
                (response["status"], encoded, utc_now(), latency_ms, model_id, request_id)).rowcount
            if changed != 1:
                raise RecordConflict("request_conflict")

    def save_feedback(self, *, submission_id, fingerprint, conversation_id, language, section, clarity, comment):
        with self._transaction() as db:
            old = db.execute("SELECT fingerprint,created_at FROM feedback WHERE submission_id=?",
                             (submission_id,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise RecordConflict("request_conflict")
                return {"status": "saved", "id": submission_id, "created_at": old["created_at"]}
            created_at = utc_now()
            db.execute("""INSERT INTO feedback
                (submission_id,fingerprint,conversation_id,language,section,clarity,comment,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (submission_id, fingerprint, conversation_id, language, section, clarity, comment, created_at))
        return {"status": "saved", "id": submission_id, "created_at": created_at}


def csv_value(value):
    text = "" if value is None else str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def export_records(database, output):
    """Read a consistent SQLite backup; CSV is display-safe, backup retains original text."""
    database, output = Path(database).resolve(), Path(output).resolve()
    if not database.is_file():
        raise FileNotFoundError("The visitor database does not exist; no empty database was created.")
    if output.exists():
        raise FileExistsError("The export directory already exists; choose a new destination.")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as source:
        source.execute("PRAGMA busy_timeout=1000")
        if source.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("Unsupported visitor database schema.")
        output.mkdir(parents=True, exist_ok=False)
        deadline = time.monotonic() + 5

        def bounded_backup(status, remaining, total):
            if time.monotonic() > deadline:
                raise RecordingUnavailable()

        with closing(sqlite3.connect(output / "records.sqlite3", timeout=1)) as backup:
            source.backup(backup, pages=128, progress=bounded_backup, sleep=.01)
    question_fields = ["request_id", "conversation_id", "created_at", "completed_at", "state", "status",
                       "question", "answer", "citations", "poster_sections", "language", "section",
                       "latency_ms", "model_id", "corpus_hash", "history_hash"]
    feedback_fields = ["submission_id", "conversation_id", "created_at", "language", "section", "clarity", "comment"]
    with closing(sqlite3.connect((output / "records.sqlite3").as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        for table, fields in [("questions", question_fields), ("feedback", feedback_fields)]:
            with (output / f"{table}.csv").open("x", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for item in db.execute(f"SELECT * FROM {table} ORDER BY created_at, rowid"):
                    row = dict(item)
                    if table == "questions":
                        response = json.loads(row.get("response_json") or "{}")
                        row.update(answer=response.get("answer", ""),
                                   citations=json.dumps(response.get("citations", []), ensure_ascii=False),
                                   poster_sections=json.dumps(response.get("poster_sections", []), ensure_ascii=False))
                    writer.writerow({key: csv_value(row.get(key)) for key in fields})
    return output
