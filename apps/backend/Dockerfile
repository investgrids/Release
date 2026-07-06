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

CMD ["gunicorn", "app.main:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
