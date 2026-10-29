"""Provision the pinned CPU bilingual voice; no service, OS voice or GPU changes."""

import argparse
import asyncio
import hashlib
import io
import json
import tarfile
import time
import urllib.request
import wave
from pathlib import Path

from orchid.config import ROOT, Settings
from orchid.speech import MODEL_NAME, MODEL_SHA256, MODEL_URL, REQUIRED_FILES, SpeechService, narration_text


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def provision(download=False):
    base = ROOT / ".cache" / "tts"
    archive = base / f"{MODEL_NAME}.tar.bz2"
    model = base / MODEL_NAME
    base.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        if not download:
            raise SystemExit("Pinned archive is missing. Run again with --download to fetch the official CPU model.")
        partial = archive.with_suffix(".part")
        started = time.monotonic()
        size = 0
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, partial.open("wb") as output:
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > 400_000_000 or time.monotonic() - started > 300:
                    raise SystemExit("Model download exceeded the fixed size/time limit; partial file retained.")
                output.write(block)
        if digest(partial) != MODEL_SHA256:
            raise SystemExit("Model archive SHA-256 mismatch; model was not extracted.")
        partial.replace(archive)
    if digest(archive) != MODEL_SHA256:
        raise SystemExit("Existing archive SHA-256 mismatch; model was not extracted.")
    if not all((model / name).is_file() for name in REQUIRED_FILES):
        with tarfile.open(archive, "r:bz2") as bundle:
            for member in bundle.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != MODEL_NAME or ".." in parts or member.issym() or member.islnk():
                    raise SystemExit("Unexpected archive path or link; model was not extracted.")
            bundle.extractall(base, filter="data")
    # Bind the local receipt to files from the checked archive, not arbitrary
    # pre-existing files with the same names. Stream comparison avoids a second extraction.
    files = {}
    with tarfile.open(archive, "r:bz2") as bundle:
        for member in bundle:
            if not member.isfile():
                continue
            relative = Path(member.name).relative_to(MODEL_NAME).as_posix()
            with bundle.extractfile(member) as source:
                expected = hashlib.file_digest(source, "sha256").hexdigest()
            local = model / relative
            if not local.is_file() or digest(local) != expected:
                raise SystemExit(f"Local model verification failed for {relative}; nothing was marked ready.")
            files[relative] = expected
    receipt = {"model": MODEL_NAME, "archive_sha256": MODEL_SHA256, "archive_url": MODEL_URL,
               "license": "Apache-2.0", "runtime": "sherpa-onnx==1.13.3", "files": files}
    (model / "provision.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": MODEL_NAME, "verified_files": len(files), "archive_sha256": MODEL_SHA256,
                      "license": "Apache-2.0", "directory": str(model)}), flush=True)


async def smoke():
    service = SpeechService(Settings())
    output = ROOT / ".orchid" / "speech-smoke"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for language, filename in (("en", "guide.en.json"), ("zh-TW", "guide.json")):
        guide = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
        texts = [("intro", guide["introduction"])] + [(item["id"], f"{item['title']}. {item['detail']}")
                                                      for item in guide["clues"]]
        for guide_id, text in texts:
            started = time.monotonic()
            normalized = narration_text(text, language)
            (output / f"{language}-{guide_id}.txt").write_text(normalized + "\n", encoding="utf-8")
            payload = await service.synthesize(text, language, guide_id=guide_id)
            (output / f"{language}-{guide_id}.wav").write_bytes(payload)
            with wave.open(io.BytesIO(payload), "rb") as stream:
                duration = stream.getnframes() / stream.getframerate()
            record = {"language": language, "guide_id": guide_id, "input_characters": len(text),
                      "narration_characters": len(normalized), "seconds": round(time.monotonic() - started, 3),
                      "audio_seconds": round(duration, 3), "bytes": len(payload),
                      "sha256": hashlib.sha256(payload).hexdigest()}
            records.append(record)
            print(json.dumps(record), flush=True)
            (output / "report.json").write_text(json.dumps({"runtime": "sherpa-onnx==1.13.3",
                                                          "threads": 2, "provider": "cpu", "results": records},
                                                         indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download the pinned official archive if missing")
    parser.add_argument("--smoke", action="store_true", help="Render all eight vetted static guide selections")
    args = parser.parse_args()
    provision(args.download)
    if args.smoke:
        asyncio.run(smoke())
