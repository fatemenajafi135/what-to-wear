FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files (respects .dockerignore, excludes .env and .venv)
COPY . .

# Create virtual environment and install dependencies from lockfile
# (reproducible, pinned versions from uv.lock)
RUN uv venv --python 3.12 && uv sync --frozen --no-dev

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Port defaults to 8000 but respects $PORT env var set at runtime
ENV PORT=8000
EXPOSE 8000

# Shell form allows $PORT environment variable expansion
CMD ["/bin/sh", "-c", ".venv/bin/uvicorn whattowear.main:app --host 0.0.0.0 --port ${PORT}"]