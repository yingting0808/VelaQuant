FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        docker-cli \
        docker-compose \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/apps/api

COPY apps/api/pyproject.toml /workspace/apps/api/pyproject.toml
COPY apps/api/app /workspace/apps/api/app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e '.[dev]'
