FROM python:3.12-slim

RUN pip install --no-cache-dir uv

# The non-root user is created BEFORE the source is copied, and the copy is
# chowned inline. The obvious ordering — copy, install, then
# `RUN useradd && chown -R appuser /app` — is correct but expensive: `chown -R`
# rewrites every file it touches into a new image layer, so the ~500 MB
# dependency tree ends up stored TWICE and the image roughly doubles (measured:
# 1.27 GB that way, and 68 s spent in the chown step alone).
# /app is chowned here while it is still EMPTY — one directory, not a
# recursive rewrite. WORKDIR would otherwise create it root-owned, and
# `COPY --chown` only sets ownership on the files it copies, not on the
# directory containing them, so `uv venv` could not create /app/.venv.
RUN useradd -m -u 1000 appuser && mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

# Respects .dockerignore, which excludes .env and legacy.env — never bake
# secrets into an image layer.
COPY --chown=appuser:appuser . .

USER appuser

# `--frozen` installs exactly what uv.lock pins rather than re-resolving, so
# the image matches what the test suite ran against. `--no-dev` leaves out
# pytest/mypy/ruff.
RUN uv venv --python 3.12 && uv sync --frozen --no-dev

# A default for local `docker run`. Render and most hosts inject their own
# PORT, which overrides this — the CMD reads it at runtime, so the image does
# not need rebuilding to listen elsewhere.
ENV PORT=8000
EXPOSE 8000

# Shell form so ${PORT} is expanded at container start, not baked in at build.
CMD ["/bin/sh", "-c", ".venv/bin/uvicorn whattowear.main:app --host 0.0.0.0 --port ${PORT}"]
