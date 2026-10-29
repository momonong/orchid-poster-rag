"""Bounded one-shot product API checks; no retries and no model API access."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8000")
parser.add_argument("--language", choices=["en", "zh-TW", "both"], default="both")
args = parser.parse_args()
target = urlparse(args.base)
if (target.scheme != "http" or target.hostname not in {"127.0.0.1", "localhost", "::1"}
        or target.username or target.password or target.query or target.fragment
        or target.path not in {"", "/"}):
    parser.error("--base must be the local app's loopback HTTP origin")
root = Path(__file__).resolve().parent.parent
cases = json.loads((root / "data/questions.en.json").read_text(encoding="utf-8"))
golden = json.loads((root / "data/golden.json").read_text(encoding="utf-8"))
expected = {item["id"]: item for item in golden}
requests = [{**case, "language": "en"} for case in cases] if args.language in {"en", "both"} else []
if args.language in {"zh-TW", "both"}:
    requests += [{**case, "language": "zh-TW"} for case in golden]
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
out = root / "output" / f"bilingual-live-{stamp}-{uuid4().hex[:8]}.json"
out.parent.mkdir(exist_ok=True)
report = {"started_utc": stamp, "state": "in_progress", "base": args.base,
          "code_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                          for path in ("orchid/app.py", "orchid/generation.py", "orchid/retrieval.py",
                                       "orchid/translations.py", "data/evidence.en.json")},
          "planned": len(requests), "results": []}

def save():
    temporary = out.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(out)

save()
with httpx.Client(base_url=args.base, timeout=80, trust_env=False) as client:
    try:
        ready = client.get("/api/health")
        ready.raise_for_status()
        health = ready.json()
    except (httpx.HTTPError, ValueError):
        report.update(state="blocked", reason="app health unavailable")
        save()
        raise SystemExit("App health unavailable; no questions sent")
    if not health["index"]["ready"] or not health["model"]["ready"] or health["queue"]["active"] or health["queue"]["pending"]:
        report.update(state="blocked", reason="not ready or active")
        save()
        raise SystemExit("App not ready or already active; no questions sent")
    for case in requests:
        entry = {"id": case["id"], "language": case["language"], "question": case["question"],
                 "history": case.get("history", []), "answerable": expected[case["id"]]["answerable"],
                 "source_any": expected[case["id"]]["source_any"], "state": "sent"}
        report["results"].append(entry)
        save()
        started = time.perf_counter()
        try:
            response = client.post("/api/chat", json={key: entry[key] for key in ("question", "history", "language")})
            response.raise_for_status()
            entry.update(response=response.json(), elapsed_seconds=round(time.perf_counter()-started, 3),
                         state="received")
        except (httpx.HTTPError, ValueError) as exc:
            entry.update(state="transport_unknown", error_type=type(exc).__name__)
            report["state"] = "stopped"
            save()
            break
        save()
        print(f"{entry['id']} {entry['language']} {entry['response']['status']} {entry['elapsed_seconds']}s", flush=True)
        if entry["response"]["status"] in {"busy", "unavailable"}:
            report["state"] = "stopped"
            break
        if entry["response"]["status"] == "unknown":
            health = client.get("/api/health").json()
            if health["queue"]["active"] or health["model"].get("result_unknown") or not health["model"]["ready"]:
                report["state"] = "stopped"
                break
    else:
        report["state"] = "complete"
save()
print(out, flush=True)
