"""Bounded CPU-only narration; answer audio is never written to disk."""

import asyncio
import hashlib
import html
import io
import json
import re
import threading
import time
import wave
from collections import OrderedDict

from .generation import Busy, GenerationQueue, Unavailable

MODEL_NAME = "kokoro-multi-lang-v1_1"
MODEL_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/{MODEL_NAME}.tar.bz2"
MODEL_SHA256 = "b78e1ac42b852e839cceaafbe88f66806bf5860992d1d7b9a3f2ad1198427aed"
MAX_TEXT_CHARS = 4000
MAX_AUDIO_BYTES = 14_400_044  # Five minutes, mono PCM16 at 24 kHz.
REQUIRED_FILES = ("model.onnx", "voices.bin", "tokens.txt", "lexicon-us-en.txt", "lexicon-zh.txt",
                  "date-zh.fst", "number-zh.fst", "phone-zh.fst", "LICENSE")


class SpeechTimeout(Exception):
    pass


def narration_text(text, language):
    """Normalize only the spoken copy; keep scientific conditions and numbers."""
    text = html.unescape(text)
    text = re.sub(r"\[[A-Z][A-Z0-9_]*\d[A-Z0-9_]*\]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\s)]+\)", r"\1", text)
    text = re.sub(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>", "", text)
    text = re.sub(r"[*`#]", "", text)
    digits = (["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"] if language == "en"
              else list("零一二三四五六七八九"))

    def spell(match):
        return " ".join(digits[int(char)] if char.isdigit() else char.upper() for char in match.group())

    text = re.sub(r"\b(?:PeMYB11|PeMYBx|HORT1|miR858)\b", spell, text, flags=re.IGNORECASE)
    def parameter(match):
        suffix = " " + " ".join(match[3].upper()) if match[3] else ""
        return f"{match[1]} {match[2]}{suffix}"

    text = re.sub(r"\b([GD])_([AH])(?:_(pur|whi))?\b", parameter, text)
    text = re.sub(r"(?:[µμ]|\bmu)_?([AH])\b", r"mu \1", text)
    text = re.sub(r"(?:ρ|\brho)_?([AH])\b", r"rho \1", text)
    text = re.sub(r"[µμ]M\b", "micromolar" if language == "en" else "微莫耳", text)
    text = text.replace(">=", "≥").replace("<=", "≤")
    comparisons = {">": ("greater than", "大於"), "<": ("less than", "小於"),
                   "=": ("equals", "等於"), "≥": ("greater than or equal to", "大於等於"),
                   "≤": ("less than or equal to", "小於等於"), "×": ("times", "乘以")}
    for symbol, names in comparisons.items():
        text = text.replace(symbol, f" {names[language != 'en']} ")
    if language == "en":
        # This shared model uses Chinese number FSTs. Spell English numerals
        # before they reach those rules, preserving every decimal digit.
        def number(match):
            return " ".join("point" if char == "." else digits[int(char)] for char in match.group())
        text = re.sub(r"(?<![\w.])\d+(?:\.\d+)*(?!\w)", number, text)
    if language == "zh-TW":
        from opencc import OpenCC
        text = OpenCC("t2s").convert(text)
    return re.sub(r"\s+", " ", text).strip()


def validate_wav(payload):
    if not 44 < len(payload) <= MAX_AUDIO_BYTES:
        raise Unavailable("Speech output is unavailable.")
    try:
        with wave.open(io.BytesIO(payload), "rb") as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 24000):
                raise ValueError("Unexpected audio format")
            frames = stream.getnframes()
            if not 0 < frames <= 24000 * 300 or len(stream.readframes(frames)) != frames * 2:
                raise ValueError("Incomplete audio")
    except (wave.Error, EOFError, ValueError) as exc:
        raise Unavailable("Speech output is unavailable.") from exc
    return payload


class SpeechService:
    def __init__(self, settings, renderer=None, *, response_seconds=100, wait_seconds=20,
                 cache_seconds=120, clock=time.monotonic):
        self.settings = settings
        self.model_dir = settings.cache / "tts" / MODEL_NAME
        self.static_cache = settings.cache / "speech"
        self.queue = GenerationQueue(max_pending=2, wait_seconds=wait_seconds)
        self.response_seconds = response_seconds
        self.clock = clock
        self.cache_seconds = cache_seconds
        self.answer_cache = OrderedDict()
        self.cache_lock = threading.Lock()
        self.renderer = renderer
        self.engine = None
        self._ready = renderer is not None or self._provisioned()

    def _provisioned(self):
        try:
            receipt = json.loads((self.model_dir / "provision.json").read_text(encoding="utf-8"))
            return (receipt["archive_sha256"] == MODEL_SHA256
                    and set(REQUIRED_FILES).issubset(receipt["files"])
                    and all((self.model_dir / name).is_file() for name in REQUIRED_FILES)
                    and (self.model_dir / "espeak-ng-data").is_dir())
        except (OSError, KeyError, ValueError):
            return False

    def health(self):
        return {"ready": self._ready, "engine": "sherpa-onnx", "languages": ["en", "zh-TW"],
                "sample_rate": 24000, "active": self.queue.active, "pending": self.queue.pending,
                "capacity": 3, "max_text_chars": MAX_TEXT_CHARS}

    def _load(self):
        if self.engine is not None:
            return
        import sherpa_onnx
        receipt = json.loads((self.model_dir / "provision.json").read_text(encoding="utf-8"))
        for name, expected in receipt["files"].items():
            path = (self.model_dir / name).resolve()
            if not path.is_relative_to(self.model_dir.resolve()):
                raise Unavailable("Speech model verification failed.")
            with path.open("rb") as source:
                actual = hashlib.file_digest(source, "sha256").hexdigest()
            if actual != expected:
                self._ready = False
                raise Unavailable("Speech model verification failed.")
        base = self.model_dir
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(base / "model.onnx"), voices=str(base / "voices.bin"),
                    tokens=str(base / "tokens.txt"), data_dir=str(base / "espeak-ng-data"),
                    lexicon=f"{base / 'lexicon-us-en.txt'},{base / 'lexicon-zh.txt'}"),
                num_threads=2, provider="cpu", debug=False),
            rule_fsts=",".join(str(base / name) for name in ("date-zh.fst", "number-zh.fst", "phone-zh.fst")),
            max_num_sentences=1)
        if not config.validate():
            self._ready = False
            raise Unavailable("Speech model configuration is unavailable.")
        self.engine = sherpa_onnx.OfflineTts(config)

    def _render(self, text, language, cancelled):
        import numpy as np
        self._load()
        deadline = self.clock() + 80
        audio = self.engine.generate(text, sid=0 if language == "en" else 3, speed=1.0,
                                     callback=lambda samples, progress: int(not cancelled.is_set()
                                                                            and self.clock() < deadline))
        if cancelled.is_set() or self.clock() >= deadline:
            raise SpeechTimeout("Speech generation timed out.")
        samples = np.asarray(audio.samples)
        if audio.sample_rate != 24000 or not 0 < len(samples) <= 24000 * 300 or not np.isfinite(samples).all():
            raise Unavailable("Speech output is unavailable.")
        output = io.BytesIO()
        with wave.open(output, "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(audio.sample_rate)
            stream.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
        return output.getvalue()

    async def synthesize(self, text, language, guide_id=None):
        if language not in {"en", "zh-TW"} or not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise ValueError("Speech text or language is invalid.")
        if not self._ready:
            raise Unavailable("Local speech is not provisioned.")
        content = narration_text(text, language)
        if not content:
            raise ValueError("Speech text is empty after removing markup.")
        key = hashlib.sha256(f"speech-v1|sherpa-1.13.3|{MODEL_SHA256}|{language}|{content}".encode()).hexdigest()
        cancelled = threading.Event()
        loop = asyncio.get_running_loop()

        def expire():
            with self.cache_lock:
                cached = self.answer_cache.get(key)
                if cached and cached[0] <= self.clock():
                    del self.answer_cache[key]

        def schedule_expiry():
            loop.call_later(self.cache_seconds + 0.01, expire)

        def produce():
            if cancelled.is_set():
                raise SpeechTimeout("Speech request was cancelled.")
            now = self.clock()
            with self.cache_lock:
                for old_key, (expiry, _) in list(self.answer_cache.items()):
                    if expiry <= now:
                        del self.answer_cache[old_key]
            path = self.static_cache / f"{key}.wav"
            if guide_id is not None and path.exists():
                return validate_wav(path.read_bytes())
            with self.cache_lock:
                if guide_id is None and key in self.answer_cache:
                    self.answer_cache.move_to_end(key)
                    return self.answer_cache[key][1]
            payload = validate_wav((self.renderer or self._render)(content, language, cancelled))
            if cancelled.is_set():
                raise SpeechTimeout("Speech request was cancelled.")
            if guide_id is not None:
                self.static_cache.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            else:
                with self.cache_lock:
                    self.answer_cache[key] = (self.clock() + self.cache_seconds, payload)
                    while (len(self.answer_cache) > 6
                           or sum(len(value[1]) for value in self.answer_cache.values()) > 24_000_000):
                        self.answer_cache.popitem(last=False)
                loop.call_soon_threadsafe(schedule_expiry)
            return payload

        async def operation():
            return await asyncio.to_thread(produce)

        try:
            # GenerationQueue shields the real worker. Cancellation signals its sentence
            # callback but never releases the slot while C++ is still running.
            return await asyncio.wait_for(self.queue.run(operation), timeout=self.response_seconds)
        except TimeoutError as exc:
            cancelled.set()
            raise SpeechTimeout("Speech generation timed out.") from exc
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except (Busy, SpeechTimeout, Unavailable, ValueError):
            raise
        except Exception as exc:
            raise Unavailable("Local speech generation failed.") from exc
