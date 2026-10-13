# Storyline web server: the Vue frontend is built in one stage and served by the FastAPI backend from another.
# Railway builds this file as-is (service variables reach the build only through ARG).

FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Baked into the bundle at build time; sign-in is off when unset.
ARG VITE_CLERK_PUBLISHABLE_KEY
# vite.config.ts writes the bundle to ../static.
RUN npm run build


FROM python:3.13-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Dependencies first so source edits do not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --locked --no-dev

COPY --from=frontend /app/static ./static

# One place for everything that must outlive a deploy; mount the Railway volume at /data.
# With AUTH_ENABLED=true each user's stories live in $STORYLINE_DATA_DIR/users/<user id>; otherwise in $STORYLINE_WORKSPACE.
ENV STORYLINE_STATIC_DIR=/app/static \
    STORYLINE_DATA_DIR=/data \
    STORYLINE_WORKSPACE=/data/workspace \
    PATH="/app/.venv/bin:$PATH"
RUN mkdir -p /data/workspace

# Railway sets PORT; 8000 is the local default.
EXPOSE 8000
CMD ["sh", "-c", "exec storyline serve --host 0.0.0.0 --port ${PORT:-8000}"]
