import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
E5_MODEL = "intfloat/multilingual-e5-small"
E5_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
QWEN_MODEL = "Qwen/Qwen3.5-4B"
QWEN_REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


@dataclass
class Settings:
    root: Path = ROOT
    model_base: str = field(default_factory=lambda: os.getenv("SELFHOST_MODEL_BASE_URL", "http://127.0.0.1:18080"))
    key_file: str = field(default_factory=lambda: os.getenv("SELFHOST_MODEL_API_KEY_FILE", ""))
    expected_model: str = field(default_factory=lambda: os.getenv("SELFHOST_MODEL_EXPECTED_ID", "Qwen/Qwen3.5-4B"))
    context_tokens: int | None = field(default_factory=lambda: int(os.environ["SELFHOST_MODEL_CONTEXT_TOKENS"])
                                      if os.getenv("SELFHOST_MODEL_CONTEXT_TOKENS") else None)
    public_url: str = field(default_factory=lambda: os.getenv("ORCHID_PUBLIC_URL", ""))
    wait_seconds: float = 35
    response_seconds: float = 44

    def __post_init__(self):
        self.root = Path(self.root)
        parsed = urlparse(self.model_base)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("模型服務必須使用同機 loopback HTTP 位址")
        self.model_base = self.model_base.rstrip("/")

    @property
    def data(self):
        return self.root / "data"

    @property
    def cache(self):
        return self.root / ".cache"

    @property
    def index(self):
        return self.root / ".orchid" / "index"
