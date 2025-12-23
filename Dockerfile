# Multi-stage build for production
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
WORKDIR /build
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Final production stage
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 buddha && \
    mkdir -p /app/logs /app/source_explorer && \
    chown -R buddha:buddha /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code (entire backend/app as package)
COPY --chown=buddha:buddha backend/app/ ./app/

# Copy RAG module (buddhist thesaurus, etc.)
COPY --chown=buddha:buddha backend/rag/ ./rag/

# Copy frontend for backend to serve
COPY --chown=buddha:buddha frontend/ ./frontend/

# Copy source explorer data structure (actual data mounted via volume)
COPY --chown=buddha:buddha backend/source_explorer ./source_explorer/

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER buddha

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run with Gunicorn (production WSGI server)
# Use stdout/stderr for logs (Docker will capture them)
CMD ["gunicorn", "app.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
