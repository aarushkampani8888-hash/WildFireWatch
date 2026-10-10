FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY frontend ./frontend
RUN npm run build

FROM python:3.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    YOLO_AUTOINSTALL=false YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib PORT=7860
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-detector-inference.txt ./
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements-detector-inference.txt
COPY backend ./backend
COPY engine.py ./
COPY demo ./demo
COPY models/smoke-detector.pt ./models/smoke-detector.pt
COPY models/detector-card.json ./models/detector-card.json
COPY deploy/start.py ./deploy/start.py
COPY --from=frontend /build/dist ./dist
RUN useradd --uid 1000 --create-home appuser && mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 7860
CMD ["python", "deploy/start.py"]
