#!/bin/bash

set -e

echo "=== Ожидание PostgreSQL ($DB_HOST:$DB_PORT) ==="
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "✓ PostgreSQL доступен"

echo "=== Применение миграций ==="
python manage.py migrate --noinput

echo "=== Создание суперпользователя ==="
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@mail.ru').exists():
    User.objects.create_superuser('admin@mail.ru', 'admin@mail.ru', 'Sas12345!')
    print('✓ Суперпользователь создан')
else:
    print('✓ Суперпользователь уже существует')
"

echo "=== Сборка статических файлов ==="
python manage.py collectstatic --noinput

echo "=== Запуск приложения ==="
exec "$@"