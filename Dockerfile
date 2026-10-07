FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --include=dev
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 FRONTEND_DIST=/app/static
WORKDIR /app

COPY backend/requirements.lock.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend /frontend/dist ./static

CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
