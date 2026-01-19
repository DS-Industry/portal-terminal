FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ВСЕ файлы проекта
COPY . .

# Делаем entrypoint исполняемым
RUN chmod +x /app/entrypoint.sh

# Указываем entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Команда по умолчанию
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=1", "--threads=8", "--timeout=0", "--access-logfile=-", "--error-logfile=-", "config.wsgi:application"]