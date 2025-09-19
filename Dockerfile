FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Запуск: ждем Postgres, миграции, создаем суперпользователя, collectstatic, gunicorn
CMD ["sh","-lc","echo 'Waiting for Postgres at ${DB_HOST}:${DB_PORT} ...' && \
until nc -z \"${DB_HOST:-db}\" \"${DB_PORT:-5432}\"; do sleep 1; done && \
echo 'Postgres is up.' && \
echo '=== Проверка текущих миграций ===' && \
python manage.py showmigrations && \
echo '=== Применение миграций ===' && \
python manage.py migrate --noinput --verbosity=2 && \
echo '=== Проверка миграций после применения ===' && \
python manage.py showmigrations && \
python manage.py shell -c \"from django.contrib.auth import get_user_model; User = get_user_model(); \
User.objects.filter(username='portal').exists() or \
User.objects.create_superuser('portal', 'portal@portal.com', 'portal')\" && \
python manage.py collectstatic --noinput && \
exec gunicorn --bind=0.0.0.0:8000 --workers 1 --threads 8 --timeout 0 --access-logfile - --error-logfile - config.wsgi:application"]
