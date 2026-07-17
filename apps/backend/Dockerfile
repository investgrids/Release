FROM python:3.11-slim

WORKDIR /app

# Install build deps for compiled packages (asyncpg, lxml, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir gunicorn uvicorn[standard] && pip install --no-cache-dir -e .

# Copy source after deps (so code changes don't bust dep cache)
COPY . .

EXPOSE 8000


# Shell form (not exec-form JSON array) so ${PORT} is expanded at container
# start -- Railway injects a dynamic PORT and routes its edge proxy to it;
# a hardcoded port here would silently break routing the moment Railway
# assigns anything other than 8000.
CMD gunicorn app.main:app \
     -w 1 \
     -k uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:${PORT:-8000} \
     --timeout 120 \
     --graceful-timeout 30 \
     --keep-alive 5 \
     --max-requests 1000 \
     --max-requests-jitter 100 \
     --access-logfile - \
     --error-logfile -
