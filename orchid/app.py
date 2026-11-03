import asyncio
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
from .localization import UNKNOWN, Language, error_text
from .records import RecordConflict, RecordingUnavailable, RecordStore, payload_hash
from .retrieval import HybridIndex
from .review import review_router
from .speech import MAX_TEXT_CHARS, SpeechService, SpeechTimeout

logger = logging.getLogger(__name__)


Section = Literal["overview", "intro", "methods", "clue1", "clue2", "clue3", "discussion", "references", "supplementary"]


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=1000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID | None = None
    conversation_id: UUID | None = None
    section: Section | None = "overview"
    question: str = Field(min_length=1, max_length=600)
    history: list[Turn] = Field(default_factory=list, max_length=4)
    language: Language = "en"

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("請輸入問題")
        return value


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: UUID
    conversation_id: UUID | None = None
    language: Language
    section: Section
    clarity: Literal["clear", "partly", "unclear"] | None = None
    comment: str = Field(default="", max_length=1500)

    @model_validator(mode="after")
    def has_feedback(self):
        if self.clarity is None and not self.comment.strip():
            raise ValueError("Feedback requires a clarity rating or a comment.")
        return self


class ProtectedStaticFiles(StaticFiles):
    def __init__(self, *args, records_file, **kwargs):
        super().__init__(*args, **kwargs)
        self.records_file = Path(records_file).resolve()

    async def get_response(self, path, scope):
        target = (Path(self.directory) / path).resolve()
        blocked = {str(self.records_file) + suffix for suffix in ("", "-wal", "-shm", "-journal")}
        if str(target) in blocked or re.search(r"\.(?:sqlite3?|db)(?:-(?:wal|shm|journal))?$", target.name, re.IGNORECASE):
            return Response(status_code=404)
        return await super().get_response(path, scope)


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    language: Language = "en"
    guide_id: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def has_content(self):
        if not self.guide_id and not self.text.strip():
            raise ValueError("Speech text is required.")
        return self


def result(status, answer, citations=None, sections=None, language="en"):
    meanings = {"en": ("Citation IDs checked; semantic accuracy still needs human review.",
                       "This is not a probability score."),
                "zh-TW": ("引用 ID 已核對；語意正確性仍需人工判斷", "不是機率分數")}
    return {"status": status, "answer": answer, "language": language, "citations": citations or [],
            "poster_sections": sections or [], "confidence": {
                "level": "citation_validated" if status == "answered" else "insufficient" if status == "unknown" else "unavailable",
                "meaning": meanings[language][0 if status == "answered" else 1]}}


def create_app(settings=None, index=None, model=None, speech=None):
    settings = settings or Settings()
    queue = GenerationQueue(wait_seconds=settings.wait_seconds)
    model = model or ModelClient(settings)
    speech = speech or SpeechService(settings)
    records = RecordStore(settings.records_file, recover_pending=True)

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(records.ready)
        if app.state.index is None:
            app.state.index = await asyncio.to_thread(HybridIndex, settings)
        await model.probe()
        yield
        if app.state.record_tasks:
            await asyncio.gather(*list(app.state.record_tasks), return_exceptions=True)
        await model.close()

    app = FastAPI(title="Orchid research poster guide", lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.state.index, app.state.queue, app.state.model, app.state.speech = index, queue, model, speech
    app.state.records = records
    app.state.record_tasks = set()
    app.include_router(review_router(settings))

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
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
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
            "speech": speech.health(),
            "recording": {"ready": await asyncio.to_thread(records.ready)},
            "queue": {"active": max(queue.active, int(model.quarantined)), "pending": queue.pending,
                      "capacity": 3, "quarantined": model.quarantined}}

    @app.get("/api/guide")
    async def guide(language: Language = "en"):
        filename = "guide.en.json" if language == "en" else "guide.json"
        return json.loads((settings.data / filename).read_text(encoding="utf-8"))

    @app.post("/api/speech")
    async def narrate(body: SpeechRequest, request: Request):
        text = body.text
        if body.guide_id is not None:
            manifest = await guide(body.language)
            if body.guide_id == "intro":
                text = manifest["introduction"]
            else:
                clue = next((item for item in manifest["clues"] if item["id"] == body.guide_id), None)
                if clue is None:
                    raise HTTPException(404, "Guide narration not found.")
                text = f"{clue['title']}. {clue['detail']}"
        task = asyncio.create_task(speech.synthesize(text, body.language, guide_id=body.guide_id))

        async def disconnected():
            # FastAPI has consumed the bounded JSON body. Wait for the actual
            # ASGI event: is_disconnected()'s immediate-cancel probe cannot pass
            # the checkpoint in BaseHTTPMiddleware's wrapped receive.
            while True:
                if (await request.receive())["type"] == "http.disconnect":
                    return

        disconnect = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait({task, disconnect}, return_when=asyncio.FIRST_COMPLETED)
            if task not in done:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return Response(status_code=499)
            return Response(await task, media_type="audio/wav", headers={"Cache-Control": "no-store"})
        except Busy as exc:
            raise HTTPException(429, "Local speech is busy. Try again when playback preparation finishes.") from exc
        except SpeechTimeout as exc:
            raise HTTPException(504, "Speech preparation timed out. No automatic retry was made.") from exc
        except Unavailable as exc:
            raise HTTPException(503, "Local speech is unavailable. You can still read the text.") from exc
        except ValueError as exc:
            raise HTTPException(422, "Speech text is invalid or too long.") from exc
        finally:
            disconnect.cancel()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, disconnect, return_exceptions=True)

    @app.get("/api/sources/{source_id}")
    async def source(source_id: str, language: Language = "en"):
        corpus = load_corpus(settings.data / "evidence.json")
        candidates = corpus + (app.state.index.chunks if app.state.index and hasattr(app.state.index, "chunks") else [])
        item = next((c for c in candidates if c["id"] == source_id), None)
        if item is None:
            raise HTTPException(404, "Source not found" if language == "en" else "找不到這個來源")
        docs = (await guide(language))["documents"]
        doc = next(d for d in docs if d["id"] == item["document"])
        labels = json.loads((settings.data / "source-labels.en.json").read_text(encoding="utf-8"))
        localized = {}
        if language == "en":
            localized = {"title": labels["titles"].get(source_id.split("_")[0], item["title"]),
                         "kind": labels["kinds"].get(item["kind"], item["kind"])}
        return {**item, **localized, "url": doc["url"], "document_title": doc["title"],
                "local_url": doc.get("local_url"), "license": doc["license"],
                "summary_language": "zh-TW", "original_language": "en",
                "excerpt_type": "Reviewed Chinese summary and annotations; not a verbatim quotation"
                if language == "en" else "人工校對的忠實摘要與校註；並非逐字引文"}

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

    async def answer_chat(body: ChatRequest):
        language = body.language
        def reply(status, answer, citations=None, sections=None):
            return result(status, answer, citations, sections, language)
        current = app.state.index
        if current is None or not current.ready:
            return reply("unavailable", "The research index is not ready. You can still read the guide and sources."
                         if language == "en" else "研究資料索引尚未就緒，目前可以先讀一分鐘導覽與來源。")
        if model.quarantined and not await model.probe():
            return reply("busy", "The previous model task has not been confirmed finished. Its generation slot is reserved; please read the guide."
                         if language == "en" else "前一題的模型工作尚未確認終止，目前保留生成名額。請先閱讀導覽。")
        history = [h.model_dump() for h in body.history]
        async def generate():
            passages = await asyncio.to_thread(current.search, body.question, history, language=language)
            if not passages:
                return {"status": "unknown", "answer": UNKNOWN[language]}, []
            return await model.generate(body.question, history, passages, language), passages
        try:
            output, passages = await asyncio.wait_for(queue.run(generate), timeout=settings.response_seconds)
        except ValueError as exc:
            return reply("unknown", error_text(str(exc), language, "unknown"))
        except Busy as exc:
            return reply("busy", error_text(str(exc), language, "busy"))
        except Unavailable as exc:
            return reply("unavailable", error_text(str(exc), language, "unavailable")
                         + (" You can still read the guide and sources." if language == "en" else "。目前可以先讀導覽與來源。"))
        except TimeoutError:
            return reply("unknown", "Generation timed out without a verified reply. The service may still be processing; the question was not resent automatically."
                         if language == "en" else "此題生成逾時，尚未取得可驗證回覆。服務仍可能在處理，沒有自動重送。")
        except UnknownResult as exc:
            return reply("unknown", error_text(str(exc), language, "unknown"))
        if (output.get("status") != "answered"
            or not validate_answer(output.get("answer"), {p["id"] for p in passages})
            or not validate_claim_scope(output["answer"])
            or not validate_numbers(output["answer"], passages)):
            return reply("unknown", UNKNOWN[language])
        used = set(re.findall(r"\[([A-Z][A-Z0-9_]*\d[A-Z0-9_]*)\]", output["answer"]))
        citations = [{k: p.get(k) for k in ("id", "title", "document", "section", "page", "figure", "kind")}
                     for p in passages if p["id"] in used]
        sections = list(dict.fromkeys(s for p in passages if p["id"] in used for s in p.get("poster_sections", [])))
        return reply("answered", output["answer"], citations, sections)

    def recording_error(exc):
        if isinstance(exc, RecordConflict):
            return HTTPException(409, detail={"code": exc.code})
        return HTTPException(503, detail={"code": "recording_unavailable"})

    def keep_task(coroutine):
        task = asyncio.create_task(coroutine)
        app.state.record_tasks.add(task)

        def finished(done):
            app.state.record_tasks.discard(done)
            if not done.cancelled():
                done.exception()  # Consume detached failures without logging visitor data.

        task.add_done_callback(finished)
        return task

    @app.post("/api/chat")
    async def chat(body: ChatRequest):
        request_id = str(body.request_id or uuid4())
        conversation_id = str(body.conversation_id or uuid5(NAMESPACE_URL, request_id))
        history_hash = payload_hash([turn.model_dump() for turn in body.history])
        fingerprint = payload_hash({"question": body.question, "language": body.language,
                                    "history_hash": history_hash, "section": body.section,
                                    "conversation_id": conversation_id})

        async def recorded_chat():
            started = time.monotonic()
            source = settings.index / "manifest.json"
            try:
                corpus_hash = await asyncio.to_thread(
                    lambda: json.loads(source.read_text(encoding="utf-8")).get("corpus_hash")
                ) if source.exists() else None
                receipt = await asyncio.to_thread(records.claim_question, request_id=request_id,
                    fingerprint=fingerprint, conversation_id=conversation_id, question=body.question,
                    language=body.language, section=body.section, history_hash=history_hash,
                    model_id=(model.info or {}).get("id", settings.expected_model), corpus_hash=corpus_hash)
                if receipt is not None:
                    return receipt
            except (RecordConflict, RecordingUnavailable) as exc:
                raise recording_error(exc) from None
            except (OSError, ValueError):
                raise recording_error(RecordingUnavailable()) from None
            try:
                response = await answer_chat(body)
            except Exception as exc:  # noqa: BLE001 -- Persist the safe visitor failure; never log content.
                logger.error("Chat processing failed: %s", type(exc).__name__)
                response = result("unavailable", "The answer could not be completed. Please read the guide."
                                  if body.language == "en" else "此題未能完成，請先閱讀導覽。", language=body.language)
            response.update(request_id=request_id, record_saved=True)
            try:
                await asyncio.to_thread(records.complete_question, request_id, response,
                    latency_ms=max(0, round((time.monotonic() - started) * 1000)),
                    model_id=(model.info or {}).get("id", settings.expected_model))
            except (RecordConflict, RecordingUnavailable) as exc:
                raise recording_error(exc) from None
            return response

        # Includes admission persistence: cancellation cannot orphan a committed pending row.
        return await asyncio.shield(keep_task(recorded_chat()))

    @app.post("/api/feedback", status_code=201)
    async def feedback(body: FeedbackRequest):
        values = body.model_dump(mode="json")

        async def saved_feedback():
            try:
                return await asyncio.to_thread(records.save_feedback,
                    fingerprint=payload_hash(values), **values)
            except (RecordConflict, RecordingUnavailable) as exc:
                raise recording_error(exc) from None

        return await asyncio.shield(keep_task(saved_feedback()))

    assets = settings.root / ".orchid" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", ProtectedStaticFiles(directory=assets, records_file=settings.records_file), name="assets")
    app.mount("/", ProtectedStaticFiles(directory=Path(__file__).parent / "static", html=True, records_file=settings.records_file), name="static")
    return app
