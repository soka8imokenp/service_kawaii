# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Python Backend
FROM python:3.11-slim

WORKDIR /app

# Установите системные зависимости
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Скопируйте и установите Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопируйте backend код
COPY core/ ./core/
COPY feedback/ ./feedback/
COPY manage.py .
COPY bot.py .
COPY create_admin.py .

# Скопируйте frontend dist из Stage 1
COPY --from=frontend-builder /app/frontend/dist ./feedback/static/dist

# Создайте папку для статических файлов
RUN mkdir -p staticfiles

# Выполните collectstatic
RUN python manage.py collectstatic --noinput --clear

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/admin/', timeout=5)"

# Запуск приложения
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60", "core.wsgi:application"]