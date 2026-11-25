FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME=/app/work/models HF_HUB_DISABLE_XET=1 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false USE_TORCH=0
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY --from=frontend /build/dist/ ./static/
RUN mkdir -p /app/work && useradd -m appuser && chown -R appuser:appuser /app
USER appuser
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
