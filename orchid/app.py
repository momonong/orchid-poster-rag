import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .corpus import load_corpus
from .generation import (
    Busy,
    GenerationQueue,
    ModelClient,
    Unavailable,
    UnknownResult,
    validate_answer,
    validate_claim_scope,
    validate_numbers,
)
from .retrieval import HybridIndex


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    history: list[Turn] = Field(default_factory=list, max_length=4)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("請輸入問題")
        return value.strip()


UNKNOWN = "目前無法根據這份海報與論文，提供通過來源核對的回答。可向現場研究人員，或通訊作者 Yu-Chen Shu（ycshu@mail.ncku.edu.tw）詢問；本頁不會代為記錄或寄送問題。"


def result(status, answer, citations=None, sections=None):
    return {"status": status, "answer": answer, "citations": citations or [],
            "poster_sections": sections or [], "confidence": {
                "level": "citation_validated" if status == "answered" else "insufficient" if status == "unknown" else "unavailable",
                "meaning": "引用 ID 已核對；語意正確性仍需人工判斷" if status == "answered" else "不是機率分數"}}


def create_app(settings=None, index=None, model=None):
    settings = settings or Settings()
    queue = GenerationQueue(wait_seconds=settings.wait_seconds)
    model = model or ModelClient(settings)

    @asynccontextmanager
    async def lifespan(app):
        if app.state.index is None:
            app.state.index = await asyncio.to_thread(HybridIndex, settings)
        await model.probe()
        yield
        await model.close()

    app = FastAPI(title="蘭花研究海報導覽", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.state.index, app.state.queue, app.state.model = index, queue, model

    @app.middleware("http")
    async def bounds_and_headers(request: Request, call_next):
        if request.method == "POST":
            try:
                if int(request.headers.get("content-length", "0")) > 16384:
                    return JSONResponse({"detail": "問題內容過長"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Content-Length 不合法"}, status_code=400)
            # Read a bounded stream, including chunked bodies with no Content-Length.
            size, parts = 0, []
            async for part in request.stream():
                size += len(part)
                if size > 16384:
                    return JSONResponse({"detail": "問題內容過長"}, status_code=413)
                parts.append(part)
            request._body = b"".join(parts)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    async def health():
        ready = await model.probe()
        current = app.state.index
        return {"app": "ready", "index": {"ready": bool(current and current.ready),
            "message": current.reason if current else "索引載入中"},
            "model": {"ready": ready, "id": model.info.get("id") if model.info else None,
                      "message": model.reason, "result_unknown": model.quarantined},
            "queue": {"active": max(queue.active, int(model.quarantined)), "pending": queue.pending,
                      "capacity": 3, "quarantined": model.quarantined}}

    @app.get("/api/guide")
    async def guide():
        return json.loads((settings.data / "guide.json").read_text(encoding="utf-8"))

    @app.get("/api/sources/{source_id}")
    async def source(source_id: str):
        corpus = load_corpus(settings.data / "evidence.json")
        candidates = corpus + (app.state.index.chunks if app.state.index and hasattr(app.state.index, "chunks") else [])
        item = next((c for c in candidates if c["id"] == source_id), None)
        if item is None:
            raise HTTPException(404, "找不到這個來源")
        docs = json.loads((settings.data / "guide.json").read_text(encoding="utf-8"))["documents"]
        doc = next(d for d in docs if d["id"] == item["document"])
        return {**item, "url": doc["url"], "document_title": doc["title"],
                "local_url": doc.get("local_url"), "license": doc["license"],
                "excerpt_type": "人工校對的忠實摘要與校註；並非逐字引文"}

    @app.get("/api/documents/{document_id}")
    async def document(document_id: str):
        manifest_path = settings.data / "sources.json"
        if not manifest_path.exists():
            raise HTTPException(404, "原始資料尚未登錄")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        item = manifest.get(document_id)
        if not item or "path" not in item:
            raise HTTPException(404, "找不到這份文件")
        target = (settings.root / item["path"]).resolve()
        if not target.is_relative_to(settings.root.resolve()) or target.suffix.lower() != ".pdf" or not target.is_file():
            raise HTTPException(404, "原始 PDF 無法取得")
        return FileResponse(target, media_type="application/pdf", filename=target.name, content_disposition_type="inline")

    @app.post("/api/chat")
    async def chat(body: ChatRequest):
        current = app.state.index
        if current is None or not current.ready:
            return result("unavailable", "研究資料索引尚未就緒，目前可以先讀一分鐘導覽與來源。")
        if model.quarantined and not await model.probe():
            return result("busy", "前一題的模型工作尚未確認終止，目前保留生成名額。請先閱讀導覽。")
        history = [h.model_dump() for h in body.history]
        async def generate():
            passages = await asyncio.to_thread(current.search, body.question, history)
            if not passages:
                return {"status": "unknown", "answer": UNKNOWN}, []
            return await model.generate(body.question, history, passages), passages
        try:
            output, passages = await asyncio.wait_for(queue.run(generate), timeout=settings.response_seconds)
        except ValueError as exc:
            return result("unknown", str(exc))
        except Busy as exc:
            return result("busy", str(exc))
        except Unavailable as exc:
            return result("unavailable", str(exc) + "。目前可以先讀導覽與來源。")
        except TimeoutError:
            return result("unknown", "此題生成逾時，尚未取得可驗證回覆。服務仍可能在處理，沒有自動重送。")
        except UnknownResult as exc:
            return result("unknown", str(exc))
        if (output.get("status") != "answered"
            or not validate_answer(output.get("answer"), {p["id"] for p in passages})
            or not validate_claim_scope(output["answer"])
            or not validate_numbers(output["answer"], passages)):
            return result("unknown", UNKNOWN)
        used = set(re.findall(r"\[([A-Z][A-Z0-9_]*\d[A-Z0-9_]*)\]", output["answer"]))
        citations = [{k: p.get(k) for k in ("id", "title", "document", "section", "page", "figure", "kind")}
                     for p in passages if p["id"] in used]
        sections = list(dict.fromkeys(s for p in passages if p["id"] in used for s in p.get("poster_sections", [])))
        return result("answered", output["answer"], citations, sections)

    assets = settings.root / ".orchid" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
    return app
