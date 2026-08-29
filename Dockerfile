# Multi-stage build (§14): build stage installs dependencies with uv, runtime
# stage copies only the venv + app code onto a slim Python base image, runs as
# a non-root user.
#
# Base image version must match .python-version (3.10, pinned for the local
# macOS vendored torch/scipy wheels) — otherwise uv detects the mismatch mid-
# build and silently downloads a standalone interpreter that doesn't survive
# the copy into the runtime stage. WORKDIR is /app in both stages (not /build
# for the build stage) because uv/pip bake the venv's own absolute path into
# every console-script shebang (e.g. `#!/app/.venv/bin/python`) at install
# time; a mismatched WORKDIR between stages breaks every script (alembic,
# gunicorn, ...) once copied.

FROM python:3.10-slim AS build

RUN pip install --no-cache-dir uv==0.5.11
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.10-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app

COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --from=build --chown=app:app /app/app /app/app
COPY --from=build --chown=app:app /app/document_extraction /app/document_extraction
COPY --from=build --chown=app:app /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# Shell form (via explicit `sh -c`, not Docker's bare shell-form CMD) so
# $WORKERS is actually substituted at container start -- previously this was
# hardcoded to 4 regardless of the WORKERS env var Settings.workers already
# read (app/core/config.py), so tuning worker count per-environment (e.g. a
# smaller pilot-scale host) required editing this file. Defaults to 4,
# matching the previous hardcoded value and local .env's WORKERS=4, so
# nothing changes unless WORKERS is set.
CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS:-4} -b 0.0.0.0:8000 app.main:app"]
