FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md requirements.lock ./
COPY src ./src

RUN python -m pip wheel --constraint requirements.lock --wheel-dir /wheels .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system research-agent \
    && useradd --system --gid research-agent --create-home research-agent

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels /wheels/research_agent-*.whl \
    && rm -rf /wheels

USER research-agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); assert response.status == 200 and json.load(response) == {'status': 'ok'}"]

CMD ["uvicorn", "research_agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
