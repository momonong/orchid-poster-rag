# Ubuntu Orchid Deployment Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans within the already authorized scope. Do not reconnect SSH, restart shared services, or push until the owner verifies the result.

**Goal:** Build a portable CPU-only Orchid container and runtime bundle for the lab Ubuntu RTX 5090 host and `https://cball.computing.ncku.edu.tw/orchid-poster/`.

**Architecture:** Keep Qwen in the existing independent selfhost-models Compose stack. Orchid uses Linux host networking and loopback only; an existing HTTPS proxy removes `/orchid-poster` before forwarding. Original PDFs, E5, tokenizer, Kokoro, assets/index and SQLite are external mounts; credentials and visitor records never enter image/Git/bundle.

**Tech Stack:** Python 3.12, uv locked dependencies, FastAPI, existing plain JavaScript, Docker Compose.

**Spec:** User request in this chat, 2026-11-02: merge/push baseline, complete Docker deployment package, target `/orchid-poster/`, defer SSH setup. Baseline `41c020ce80488f72c253a4d72e048a77a5b07b22`.

## Global Constraints

- Preserve current ngrok website, model and other GPU jobs. No new GPU tests or model downloads.
- Use the existing feature worktree sequentially; branch `feat/ubuntu-deployment`.
- Single app process, existing request queue; no Whisper or microphone feature.
- Keep English default, Traditional Chinese option, original English poster, Menu and all existing controls.
- Use image allowlist copies; raw PDF, model files, API key, SQLite/WAL, exports, logs and `.git` are excluded.
- Do not resynchronize the running Windows venv after changing torch source; validate new dependency resolution in an isolated Linux build.
- Remote installation and actual lab HTTPS acceptance remain pending SSH authentication; do not claim deployed.

## Review Focus

- URLs must remain under the prefix for images/srcset, prepared WAV, speech, citations/PDFs, chat/feedback, help screenshots and legacy homepage.
- Static redirect with no trailing slash must preserve the configured prefix.
- Runtime must not contain CUDA packages or request GPU devices.
- SQLite mounts include its directory and sidecars; synthetic tests never open the real visitor database.
- Bundling rejects symlink/path escapes, hashes actual files, and cannot pick up secrets or visitor records.

## Task 1: Application prefix compatibility

**Files:** New `orchid/static/urls.js`; modify both HTML entrypoints, `app.js`, `speech.js`, `tour-preview/tour.js`, `config.py`, `app.py`; focused existing/new URL and API tests.

**Interface:** `createAppURL(scriptURL)` creates a resolver for root-relative application URLs based on the loaded helper script directory; external URLs stay unchanged. Expose the browser resolver to both clients; keep pure CommonJS exports for Node tests. Add optional validated `ORCHID_ROOT_PATH`, default empty; proxy contract strips prefix.

- [x] Add a regression proving root and `/orchid-poster/` requests/assets stay correctly scoped, including safe external links and audio manifests.
- [x] Implement relative static HTML resources and apply the resolver consistently without monkeypatching global fetch.
- [x] Test prefixed API/static redirects and full tour operations with existing bounded browser fixtures; no real POST or audio generation.
- [x] Run affected checks, then the complete existing Node/Python suites once final changes settle.

## Task 2: CPU image and Compose

**Files:** `Dockerfile`, `.dockerignore`, `compose.yaml`, `deploy/.env.example`, `pyproject.toml`, `uv.lock`, `docs/deployment.md`, README entry.

- [x] Make torch a direct dependency from the official CPU index on Linux/Windows and preserve existing locked versions where compatible; no pip overrides.
- [x] Pin Python 3.12.14 and uv 0.12.15 image digests. Explicitly COPY only package/data/scripts/lock metadata. Install libgomp if required by runtime wheels.
- [x] Keep UID/GID compatible with private host files, read-only rootfs, writable tmp/speech/record directories, no GPU/socket mount, one process, 120s graceful stop.
- [x] Use `network_mode: host`, existing loopback API contract, optional app port and root path. Model key is a read-only file secret.
- [x] Validate Compose and build Linux amd64 image; inspect/import runtime and assert torch CUDA is absent. Do not change Docker Desktop settings or shared containers.

## Task 3: Portable runtime artifacts and handoff

**Files:** `scripts/build_deployment_bundle.py`, focused bundle tests, `docs/deployment.md` and ignored release output.

- [x] Create an allowlisted archive of registered PDFs, generated assets/index, complete existing CPU E5/Kokoro and fixed tokenizer. Exclude Qwen weights, visitor records, secrets and arbitrary caches.
- [x] Include a machine-readable file hash manifest, baseline/source commit, exact model revisions and image reference. Verify before extraction/use; reject unsafe links and paths.
- [x] Use independent container/synthetic records to smoke-test source/index/tokenizer, CPU inference/audio and persistence/CSV export without using production DB or Qwen GPU.
- [x] Export built image and runtime archive to ignored output with SHA-256 receipts and exact load/start/stop/backup commands.
- [x] Record verified Linux-container results separately from pending Ubuntu host, proxy and physical phone acceptance. Main owner reviews before any integration/push.

## Implementation evidence (2026-11-02)

- Python143/143, Node35/35 at root and35/35 under prefix, Ruff and Compose config passed.
- Final Linux CPU image: `sha256:c1386d19bbf048b42d7238cb60f9975a2a1f6bcf87fd0c16b3d3eec0084fbd35`.
- Offline CPU smoke:35chunks x384, torch2.15.0+cpu, genuine English/Chinese WAV53700/59130bytes, synthetic record persistence/export passed.
- Actual isolated Uvicorn HTTP: tour/helper/assets/prepared WAV/PDF200, native prefixed redirect passed.
- Runtime451files with verified hashes; image/runtime archive and delivery receipts under ignored `output/deployment-20261102` on primary D:checkout.
- Ubuntu/real proxy/HTTPS/physical phone acceptance remain pending; no SSH or remote changes. Parent owns independent review and Git integration.
