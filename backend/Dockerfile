# The Telcron backend: one image, two services. The API is the default command; the Worker runs
# the same image with `python -m app.workers.main`.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --system --uid 10001 --no-create-home telcron
USER telcron
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Behind the reverse proxy in the same compose network; port 8000 is never published.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
