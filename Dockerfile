# The agent's HTTP API + web chat. Built by docker-compose.yml, or alone:
#   docker build -t agentes-ia . && docker run -p 8000:8000 -e AGENTES_API_KEY=... agentes-ia
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md LICENSE ./
COPY src ./src
COPY configs ./configs
COPY data ./data
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 agente \
    && mkdir /data && chown agente /data
USER agente
VOLUME /data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["agentes", "serve", "configs/despacho-juridico.yaml", "--host", "0.0.0.0", "--data", "/data"]
