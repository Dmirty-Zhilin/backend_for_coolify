# Dockerfile для бэкенда
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директории для отчетов
RUN mkdir -p /app/reports

# Переменная окружения для порта и PYTHONPATH
ENV PORT=8000
ENV PYTHONPATH=/app

# Запуск приложения
CMD gunicorn --bind 0.0.0.0:${PORT} main:app
