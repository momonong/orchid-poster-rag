"""Prepare the twelve fixed overview clips through an already-running local speech API."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.parse
import urllib.request
import wave
from pathlib import Path


def build(root: Path, base_url: str) -> Path:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Use the existing loopback HTTP speech service; this script does not start a service.")
    root = root.resolve()
    data_path = root / "orchid" / "static" / "tour-preview" / "tour-data.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in data["sections"]}
    output = root / ".orchid" / "assets" / "tour-preview" / "audio"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": 1, "complete": False, "items": [], "total_duration_seconds": {}}
    for language in ("en", "zh-TW"):
        guide_name = "guide.en.json" if language == "en" else "guide.json"
        guide = json.loads((root / "data" / guide_name).read_text(encoding="utf-8"))
        vetted = {"intro": guide["introduction"],
                  **{item["id"]: f"{item['title']}. {item['detail']}" for item in guide["clues"]}}
        total = 0.0
        for section_id in data.get("tour_order", data["order"]):
            text = by_id[section_id][language]["narration"]
            request_body = {"language": language, "guide_id": section_id} if vetted.get(section_id) == text else {"language": language, "text": text}
            body = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(base_url.rstrip("/") + "/api/speech", data=body,
                                             headers={"Content-Type": "application/json", "Accept": "audio/wav"})
            # Sequential; a failure stops the build. There is no automatic retry or model startup.
            with urllib.request.urlopen(request, timeout=180) as response:
                audio = response.read()
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 24000):
                    raise ValueError(f"Unexpected WAV geometry: {language}/{section_id}")
                if not wav.getnframes():
                    raise ValueError(f"Empty WAV: {language}/{section_id}")
                duration = wav.getnframes() / wav.getframerate()
            filename = f"{language}-{section_id}.wav"
            destination = output / filename
            temporary = destination.with_suffix(".wav.tmp")
            temporary.write_bytes(audio)
            temporary.replace(destination)
            manifest["items"].append({"language": language, "id": section_id,
                                      "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                      "audio_sha256": hashlib.sha256(audio).hexdigest(),
                                      "url": f"/assets/tour-preview/audio/{filename}",
                                      "duration_seconds": duration, "bytes": len(audio),
                                      "request_mode": "guide_id" if "guide_id" in request_body else "text",
                                      "sample_rate": 24000, "channels": 1})
            total += duration
            print(f"{language}/{section_id}: {duration:.3f}s, {len(audio)} bytes", flush=True)
        manifest["total_duration_seconds"][language] = total
    manifest["complete"] = True
    destination = output / "manifest.json"
    temporary = output / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(build(args.root, args.base_url))
