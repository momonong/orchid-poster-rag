# Implementation progress — docs/implementation-plan.md

## Identity and authorization

- User explicitly requested implementation of the approved plan on 2026-10-29 in this chat.
- Workspace: D:/projects/orchid-poster-rag; initial HEAD 86269781c9d6d2ccdca852e26234a391fb7c512b.
- Branch: feat/orchid-poster-guide. Git delivery (commit/push/merge) not requested.
- One Sol implementation agent modifies product files. Root reviews and handles read-only runtime/source verification. No parallel source editors, so no additional worktree.

## Preflight interface scan

| Units | Producer / consumer | Resolution |
| --- | --- | --- |
| Corpus → retrieval | Provenance-bearing chunks, E5 vectors | Preserve stable source IDs and index manifest hash; unavailable dense index must not be reported as fully ready. |
| Retrieval → answer | Four passages and prior-turn context | Only passages are evidence; citations validate against this request. |
| Model → queue/UI | Complete output or explicit failure | No partial output treated as complete; cancellation must not release active capacity prematurely. |
| Guide → UI | Source-grounded static introduction/Clue content | Available without generation; poster explicitly absent until supplied. |
| App → ngrok/QR | Loopback application and actual public URL | Expose application only; QR cannot contain a guessed URL. |
| Implementation → evaluation | Live and fixture modes | Keep offline tests, actual model quality, public access and phone acceptance separate. |

## Progress

- Read-only baseline confirmed. Function branch created; no existing code or tests to run.
- User supplied the poster and corrected paper PDFs in the repository. Poster rendered and visually checked; Clue 1–3 regions and Methods located. Original files are preserved.
- Source audit: 21 curated records checked against poster/paper; unsupported translation, one paper page locator, overly absolute spot-fusion wording and model-variable interpretation corrected by the implementer.
- CPU embedding model downloaded at pinned revision; final index has 32 chunks (maximum 480 embedding tokens including prefix). All 17 answerable questions in the 21-case fixed set retrieve at least one designated source. This is retrieval evidence, not generated-answer quality.
- ngrok 3.39.10 recovered from existing official cached archive into ignored .tools/ngrok/ngrok.exe. Authenticode signature valid; existing user configuration validated without printing credentials.
- selfhost-models checkout is clean at 45ebfd57db5313292ae8f38e733f3e2894a99e5f. Registered Qwen3.5-4B revision and cached 0.2.0 API/vLLM digests match published deployment instructions. No model containers or ownership volume active; existing lease journal is empty.
- NeuroAI core remains running with an NVIDIA GPU device request. No other service has been stopped, reconfigured or restarted. Model loading needs a confirmed non-conflicting GPU window; live answer quality remains unverified. This is a shared-resource constraint, not a missing-weight or source-code failure.
- Implementation and focused offline verification finished: 19 tests pass, Ruff/JavaScript syntax/diff whitespace checks pass. Independent read-only review found no remaining high-confidence major engineering issues after tokenizer/context, malformed model response, queue admission and process ownership fixes.
- Live app is running on loopback port 8000; app and CPU hybrid index are ready. Model remains unavailable. Safe stop/start was exercised on this task's own process tree.
- ngrok HTTPS is active at https://6e1b-140-116-158-107.ngrok-free.app ; QR saved in output/guide-qr.png. Browser testing covered the actual first-visit ngrok confirmation, mobile viewport, guide tabs, source excerpts, poster, unavailable response and clear chat. See browser-validation.md.
- User was asked whether to retain NeuroAI and deliver this state, or authorize pausing neuroai_core and starting the existing Qwen service. No reply is treated as authorization; shared services remain unchanged.
- Pending acceptance: live Qwen semantic/numeric quality and latency; physical phone over cellular and actual QR scanning. No commit, push or merge performed.

## 5090 Laptop deployment continuation

- User authorized testing deployment on this laptop. Existing fixed Qwen3.5-4B/vLLM images and registered weights now run at loopback 18080, context 8192, max_inflight 1 and GPU budget 0.60. Other services including NeuroAI remain running and unchanged.
- Model readiness/capabilities, authenticated general response, SSE completion and invalid-key rejection verified. Initial cold JIT finished without manual model restart or deleting lease state.
- Live findings led to focused scope/JSON/date fixes and P09 source clarification; current corpus index has 33 chunks. Final engineering verification: 41 tests passed, Ruff and diff whitespace checks passed.
- Final 21-case product API run: 16/17 answerable pass independent source review, 4/4 unanswerable correctly abstain; G07 remains a conservative abstention. Median latency 3.75 seconds, range 2.75–6.078 seconds. This is fixed-case evidence, not universal correctness or human acceptance.
- Three independent simultaneous visitors completed in 3.188/6.797/10.641 seconds with their separate contexts. Synthetic source injection did not trigger the attack instruction, but extra unsupported explanation remains a stated limitation.
- App, model and ngrok remain available for trial. See laptop-live-test.md and output/live-quality-review.json. Physical phone cellular/QR and user acceptance remain pending; no Git delivery performed.
