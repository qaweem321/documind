# syntax=docker/dockerfile:1

FROM python:3.13.15-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    FASTEMBED_CACHE_PATH=/models
WORKDIR /app

FROM base AS build
RUN pip install --no-cache-dir uv==0.12.21
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# Bake the embedding model into the image, so containers start without downloading it.
RUN .venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

FROM base AS app
RUN useradd --system --uid 1001 app
COPY --from=build /app/.venv /app/.venv
COPY --from=build --chown=app /models /models
COPY app ./app
COPY examples ./examples
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
