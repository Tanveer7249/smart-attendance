# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend + Unified Server
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application
COPY backend ./backend
COPY run.py ./

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create user with UID 1000 (required for Hugging Face Spaces) and grant permissions to /app
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/backend"
ENV FRONTEND_DIST_DIR="/app/frontend/dist"
ENV PORT=7860
ENV HOST="0.0.0.0"

# Expose default port (7860 for Hugging Face Spaces, Koyeb/Railway dynamically override PORT)
EXPOSE 7860

# Run unified server
CMD ["python", "run.py"]

