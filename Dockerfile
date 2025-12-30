# ===========================================
# Stage 1: Build Pali Studio (React/Vite)
# ===========================================
FROM node:20-alpine AS pali-builder

WORKDIR /build

# Copy package files first (better layer caching)
COPY frontend/pali-studio/package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy source and build
COPY frontend/pali-studio/ ./
RUN npm run build

# ===========================================
# Stage 2: Build Python dependencies
# ===========================================
FROM python:3.11-slim AS python-builder

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

# ===========================================
# Stage 3: Final production image
# ===========================================
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 buddha && \
    mkdir -p /app/logs /app/source_explorer && \
    chown -R buddha:buddha /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from python-builder
COPY --from=python-builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code (entire backend/app as package)
COPY --chown=buddha:buddha backend/app/ ./app/

# Copy Pali Studio module (from nikaya_gemini)
COPY --chown=buddha:buddha backend/pali/ ./pali/

# Copy RAG module (buddhist thesaurus, etc.)
COPY --chown=buddha:buddha backend/rag/ ./rag/

# Copy frontend for backend to serve
COPY --chown=buddha:buddha frontend/ ./frontend/

# Copy Pali Studio build output from pali-builder stage
COPY --from=pali-builder --chown=buddha:buddha /build/dist/ ./frontend/pali-studio/dist/

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
