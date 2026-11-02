# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.15@sha256:62f8c047d0a0e9ece6b53fc63df902585a67a47a7f318ddec4a37db586edc8e3 AS uv
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 \
    UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/tmp/huggingface \
    ORCHID_RECORDS_FILE=/var/lib/orchid/visitor-records.sqlite3
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
RUN .venv/bin/python -c "import torch, sherpa_onnx; assert torch.version.cuda is None"
COPY orchid ./orchid
COPY data ./data
COPY scripts/build_deployment_bundle.py scripts/deployment_smoke.py ./scripts/
RUN mkdir -p .orchid/assets .orchid/index .cache/speech /var/lib/orchid
USER 1000:1000
STOPSIGNAL SIGTERM
CMD ["python", "-m", "orchid.cli", "serve", "--port", "8000"]
