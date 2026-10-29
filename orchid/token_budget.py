import hashlib
import json
import shutil
from pathlib import Path

from .config import QWEN_MODEL, QWEN_REVISION


def prepare_tokenizer(settings, local_dir=None):
    target = settings.cache / "qwen-tokenizer"
    target.mkdir(parents=True, exist_ok=True)
    if local_dir:
        # Caller has verified that the local deployment is the registered fixed revision.
        shutil.copyfile(Path(local_dir) / "tokenizer.json", target / "tokenizer.json")
        origin = "verified local deployment tokenizer"
    else:
        from huggingface_hub import hf_hub_download
        hf_hub_download(QWEN_MODEL, "tokenizer.json", revision=QWEN_REVISION, local_dir=target)
        origin = "official Hugging Face fixed revision"
    digest = hashlib.sha256((target / "tokenizer.json").read_bytes()).hexdigest()
    (target / "provenance.json").write_text(json.dumps({"model": QWEN_MODEL, "revision": QWEN_REVISION,
        "sha256": digest, "origin": origin}), encoding="utf-8")


def load_token_counter(settings):
    from tokenizers import Tokenizer
    target = settings.cache / "qwen-tokenizer"
    meta = json.loads((target / "provenance.json").read_text(encoding="utf-8"))
    path = target / "tokenizer.json"
    if (meta["model"] != QWEN_MODEL or meta["revision"] != QWEN_REVISION
        or hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]):
        raise ValueError("生成 tokenizer 的版本或檔案指紋不符")
    tokenizer = Tokenizer.from_file(str(path))
    return lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
