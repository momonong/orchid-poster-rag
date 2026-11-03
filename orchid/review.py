"""Opt-in private review UI. Reads existing records without migrations or writes."""
import asyncio
import hmac
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse


def read_records(path, *, kind, q, language, status, limit, offset):
    # No RecordStore.initialize(), journal-mode changes, recovery or backup here.
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            totals = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                      for table in ("questions", "feedback")}
            where, params = [], []
            if q:
                literal = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                if kind == "questions":
                    where.append("(question LIKE ? ESCAPE '\\' OR response_json LIKE ? ESCAPE '\\')")
                    params.extend([literal, literal])
                else:
                    where.append("comment LIKE ? ESCAPE '\\'")
                    params.append(literal)
            if language:
                where.append("language=?")
                params.append(language)
            if status and kind == "questions":
                where.append("status=?")
                params.append(status)
            clause = " WHERE " + " AND ".join(where) if where else ""
            total = db.execute(f"SELECT count(*) FROM {kind}" + clause, params).fetchone()[0]
            fields = ("request_id AS id,question,language,section,created_at,completed_at,latency_ms,state,status,response_json"
                      if kind == "questions" else "submission_id AS id,language,section,clarity,comment,created_at")
            rows = db.execute(f"SELECT {fields} FROM {kind}" + clause
                              + " ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?", [*params, limit, offset])
            items = []
            for row in rows:
                item = dict(row)
                if kind == "questions":
                    raw = item.pop("response_json")
                    try:
                        response = json.loads(raw) if raw else {}
                        if not isinstance(response, dict):
                            raise TypeError("Invalid stored reply")
                    except (ValueError, TypeError):
                        response = {"answer": "已儲存的回答無法解析。"}
                    answer = response.get("answer")
                    item["answer"] = answer if isinstance(answer, str) else ""
                    citations = response.get("citations", [])
                    item["citations"] = [c["id"] for c in citations
                        if isinstance(c, dict) and isinstance(c.get("id"), str)] if isinstance(citations, list) else []
                items.append(item)
            return {"kind": kind, "totals": totals, "total": total, "items": items,
                    "limit": limit, "offset": offset}
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "提問紀錄目前無法讀取，請稍後再試。") from None


def review_router(settings):
    router = APIRouter()

    async def authorize(request: Request):
        try:
            if not settings.review_key_file:
                raise ValueError("Review is disabled")
            expected = await asyncio.to_thread(Path(settings.review_key_file).read_text, encoding="utf-8")
            expected = expected.strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", expected):
                raise ValueError("Invalid review configuration")
        except (OSError, ValueError):
            raise HTTPException(503, "審閱入口尚未啟用，請聯絡管理者。") from None
        received = request.headers.get("authorization", "")
        if not hmac.compare_digest(received.encode("utf-8"), ("Bearer " + expected).encode("ascii")):
            # The UI sends the header explicitly; never set a browser-persisted Basic login.
            raise HTTPException(401, "請輸入正確的審閱密碼。")

    @router.get("/review", response_class=HTMLResponse)
    @router.get("/review/", response_class=HTMLResponse)
    async def shell(request: Request):
        template = (Path(__file__).parent / "static/review/index.html").read_text(encoding="utf-8")
        return HTMLResponse(template.replace("__ROOT__", request.scope.get("root_path", "")))

    @router.get("/review/api/records", dependencies=[Depends(authorize)])
    async def records(
        kind: Literal["questions", "feedback"] = "questions",
        q: str = Query(default="", max_length=200),
        language: Literal["", "en", "zh-TW"] = "",
        status: Literal["", "answered", "unknown", "busy", "unavailable", "pending", "interrupted"] = "",
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=1_000_000),
    ):
        return await asyncio.to_thread(read_records, settings.records_file, kind=kind, q=q,
                                       language=language, status=status, limit=limit, offset=offset)

    return router
