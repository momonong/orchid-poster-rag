# 蘭花研究海報 RAG 導覽系統：第一版

Approved by the user on 2026-10-29. Implementation scope: one mobile-first website for 1–3 concurrent visitors. QR → ngrok HTTPS → this Windows RTX 5090 Laptop → local selfhost-models service. No cloud generation, voice, accounts, upload admin, permanent conversations or automatic online retrieval.

## Product and evidence contract

- Taiwan Traditional Chinese, friendly academic guide, conclusion before explanation. One-minute introduction, Clue 1–3, paper/poster view, question input, follow-up and clear chat.
- Sources: corrected official paper https://link.springer.com/article/10.1186/s12870-024-05305-z ; correction https://link.springer.com/article/10.1186/s12870-024-05475-w ; user-provided poster when available. Poster currently absent: do not fabricate poster text/coordinates or pretend paper figures are the poster.
- Prepare corpus offline with provenance/version/section/figure/page where actually known. Preserve equations, parameters and experimental conditions. Separate model assumptions, simulations and experimental observations. The role prompt's overview is not independently verified evidence. Abstract wording on miR858 degradation conflicts with the Methods definition: annotate and use the actual activator degradation definition, do not silently alter original quotations.
- Answer from retrieved passages only; last two turns are conversational context, not evidence. Citation IDs must be from this request. Unknown information must be acknowledged with verified contact information; no claim to have recorded or sent a question.

## Technical decisions

- Python 3.12 + uv, FastAPI serves static HTML/CSS/JS and APIs; no frontend build framework or vector server.
- POST /api/chat accepts question and bounded history; returns answer/status/citations/poster_sections. GET /api/sources/{id} returns excerpt and provenance; GET /api/health reports app/index/model readiness without secrets. Add minimal read-only guide manifest endpoint if needed for static text and sources.
- CPU intfloat/multilingual-e5-small, query/passages prefixes, normalized vectors saved locally; pin model revision. BM25 plus vector retrieval, RRF fusion, top four passages. Chunk <=480 embedding tokens including title/prefix; never silently truncate; preserve conditions and equations. NumPy local storage.
- selfhost-models contract at commit 45ebfd57db5313292ae8f38e733f3e2894a99e5f; repo D:/projects/selfhost-models. Target Qwen/Qwen3.5-4B (registered revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a), 8192 context, max output 512, temperature 0/top_p 1, no thinking. Read ready/models first, use actual model/capabilities, no unsupported response_format/embedding routes. Model URL/key file configurable, no secrets copied into repo/browser/logs.
- One generation per user question; validate citations before complete JSON response. Do not display unvalidated partial output. Treat missing/invalid citation or inadequate evidence as insufficient evidence, not success. Semantic faithfulness remains acceptance work, not proven by citation syntax.
- One active generation plus at most two pending; bounded wait, explicit busy/unavailable/unknown status, no automatic retry on timeout/disconnect. Preserve in-flight occupancy until actual request terminal status; cancellation must not falsely free GPU capacity.
- Stateless per-request browser history, no saved user text in logs. Clear chat invalidates stale responses. Prevent XSS by rendering generated content as text/safe controlled markup. API body/history bounds, no arbitrary file serving or admin credentials exposed.
- App binds 127.0.0.1:8000 (configurable); model remains loopback. ngrok exposes app only. QR must use actual configured HTTPS public URL. Existing ngrok account only; no token in command args/chat. Account/interstitial/mobile access are separately verified.

## Work and validation

1. Single Sol implementer owns project source, tests, README and dependency files, with focused red/green tests for real behavioral risks. Root owns this plan/progress notes, evidence collection, external runtime investigation and review. No simultaneous code writers.
2. Corpus/guide + hybrid index; app/local model client/queue; mobile UI; startup/index/evaluation/QR commands; README and about twenty golden cases.
3. Test core clues, precise parameters, Chinese→English retrieval, follow-up, unsupported experiments, unnecessary universal causality, malformed citations, prompt injection, unavailable model, queue/timeout and isolated users. Goal: >=90% of answerable golden questions meet verified key points, zero numeric/citation mistakes, all unanswerable cases avoid fabrication. Record real model output separately from fixtures.
4. Browser QA, mobile viewport, source buttons, keyboard/touch/clear behavior, real HTTP/ngrok/QR. Actual phone over cellular remains a distinct human test when not accessible. Warm single-user response <=30s is a target to measure, not an asserted result.

## Preconditions and boundaries

The repo started clean at 86269781c9d6d2ccdca852e26234a391fb7c512b; current branch feat/orchid-poster-guide. No commit/push/merge requested. Do not change other projects' tracked files, restart shared services or interrupt existing GPU jobs. The default model endpoint refused connection at planning time; ngrok was not on PATH; poster not supplied. Report absent dependencies explicitly and complete all independent implementation and offline verification. Never label fixture responses as a live RAG demonstration.
