# Read-only visitor review implementation plan

**Goal:** Add `/orchid-poster/review` for the research team to read saved questions, validated replies and feedback, then deploy without losing records or changing the visitor tour.

**Architecture:** Keep FastAPI and existing SQLite schema. An isolated router opens `mode=ro` connections with `query_only`, bounded pagination and parameterized search. The public page shell contains no visitor data; private API requests require a separate random review password, kept in memory by the browser and in a Docker file secret on the server. No cookies, URL credentials, new dependencies, model calls or database migrations.

**Design:** Simple light review inbox with questions/feedback tabs, search, language and answer-status filters, newest-first expandable replies, refresh and logout. Chinese labels for the research team; original visitor text is preserved. Follow existing system typography; quiet borders, navy poster identity and restrained status colors. No charts or fabricated metrics. Desktop and 390px phone layouts.

**Approaches:** Use the existing app rather than a second admin service or CSV exports: fewer moving parts and live WAL-consistent reads. A separate Compose review override makes access opt-in and leaves existing base deployment configuration compatible. Random shared password is sufficient for this small team; no account-management system.

**Constraints:** No edits/deletes/exports in the review UI. Never render visitor HTML. Never log credentials or records. Preserve database schema, history, runtime mounts, speech cache, model service and unrelated workloads. App recreation is the only production interruption. Back up SQLite online first; compare every preexisting row using local digests without printing visitor data. Keep old image for rollback, never restore an old DB over new submissions.

## Tasks

- [x] Add focused failing tests: denied/missing auth, bounded authenticated reads, literal search, filtering, pagination, safe response fields, no DB writes, concurrent recording, prefix URLs and static shell without data.
- [x] Implement `orchid/review.py`, small settings/router integration, `orchid/static/review/` HTML/CSS/JS, and opt-in `deploy/compose.review.yaml`.
- [x] Run Python regression suite, Ruff and existing Node checks. Browser-test login, record rendering, XSS payload as text, filters, logout and phone layout using synthetic SQLite only.
- [x] Build a new Linux CPU image from the existing locked Dockerfile/cache; deploy only the app, with private review secret and pre-update SQLite backup. Preserve all old rows and other container identities.
- [x] Verify public HTTPS review shell, unauthorized denial, authenticated live review, guide/assets/health/audio and mounted DB identity. Document access, deploy and rollback; report actual validation and any remaining limitations.

## Execution notes

- App style: Achromatic ledger, seed2138811452; preserved the existing navy poster identity/system type and used a centered list instead of a dealt icon rail because only two destinations need labels.
- Linux synthetic smoke initially inherited the image's production DB path on its read-only filesystem; reran with an explicit `/tmp/review-check.sqlite3`. No production DB was mounted or modified by smoke.
- One initial asset probe used a nonexistent manifest path; corrected to `/assets/tour-preview/manifest.json` from the actual frontend code and revalidated both language WAVs.
- Credential download was initially denied by automatic review. User explicitly approved the exact private Windows destination, then transfer succeeded with a user-only ACL. No credentials were printed or staged.
- Review agent `review_access_audit` read only source/test/docs, found no blocking P1/P2 issue, and did not access credentials, visitor records or the deployment machine.
