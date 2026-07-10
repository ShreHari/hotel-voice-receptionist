# syntax=docker/dockerfile:1

# Stage 1: build the dependencies in an isolated venv
FROM python:3.12-slim AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
# copy requirements first so this layer caches until they change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# bring across only the finished venv to keep the image small
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# the agent spawns the MCP server as a subprocess, so it ships in the same image
COPY ./app ./app
COPY ./mcp_server ./mcp_server
COPY ./static ./static

# run as a non-root user; SQLite needs a writable data dir owned by that user
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data
USER appuser

EXPOSE 8100

# bind to the platform's assigned PORT when provided (e.g. Render), default 8100 locally
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
