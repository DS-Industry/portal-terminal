# Руководство по развертыванию в Yandex Container Registry

Это руководство описывает процесс сборки и публикации Docker-образа приложения в Yandex Container Registry (YCR).

## Предварительные требования

1. **Yandex Cloud CLI (yc)**
   - Установите и настройте Yandex Cloud CLI: https://cloud.yandex.ru/docs/cli/quickstart
   - Выполните авторизацию: `yc init`

2. **Docker**
   - Установленный и запущенный Docker
   - Доступ к Yandex Container Registry

3. **Доступ к реестру**
   - Registry ID: `crp7i0e7br8dlil8465r`
   - Убедитесь, что у вас есть права на запись в реестр

## Настройка Docker для работы с Yandex Container Registry

Перед первым использованием настройте Docker для работы с YCR:

```bash
yc container registry configure-docker
```

Эта команда настроит аутентификацию Docker для работы с вашим реестром.

## Сборка и публикация образа

### Вариант 1: Использование скрипта (рекомендуется)

Используйте готовый скрипт `build-and-push.sh`:

```bash
# Сделайте скрипт исполняемым (первый раз)
chmod +x build-and-push.sh

# Сборка и публикация с автоматическим тегом (git commit hash)
./build-and-push.sh

# Или с указанием конкретного тега
./build-and-push.sh v1.0.0
```

### Вариант 2: Ручная сборка и публикация

```bash
# 1. Настройка переменных
REGISTRY_ID="crp7i0e7br8dlil8465r"
IMAGE_NAME="portal-terminal"
REGISTRY_HOST="cr.yandex"
FULL_IMAGE_NAME="${REGISTRY_HOST}/${REGISTRY_ID}/${IMAGE_NAME}"
TAG="v1.0.0"  # или используйте git commit hash

# 2. Сборка образа
docker build -t "${FULL_IMAGE_NAME}:${TAG}" -t "${FULL_IMAGE_NAME}:latest" .

# 3. Публикация в реестр
docker push "${FULL_IMAGE_NAME}:${TAG}"
docker push "${FULL_IMAGE_NAME}:latest"
```

## Проверка образа в реестре

После публикации образ доступен по адресу:
```
cr.yandex/crp7i0e7br8dlil8465r/portal-terminal:<tag>
```

Проверить список образов в реестре можно через веб-консоль Yandex Cloud или через CLI:

```bash
yc container image list --registry-id crp7i0e7br8dlil8465r
```

## Использование образа

### Запуск контейнера локально

```bash
docker pull cr.yandex/crp7i0e7br8dlil8465r/portal-terminal:latest

docker run -d \
  --name portal-terminal \
  -p 8000:8000 \
  --env-file .env \
  cr.yandex/crp7i0e7br8dlil8465r/portal-terminal:latest
```

### Использование в Yandex Cloud (Kubernetes, Compute Cloud и т.д.)

Образ можно использовать в любых сервисах Yandex Cloud, которые поддерживают Docker:
- Yandex Kubernetes Engine (YKE)
- Yandex Compute Cloud (виртуальные машины)
- Yandex Serverless Containers

Пример для Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: portal-terminal
spec:
  replicas: 1
  selector:
    matchLabels:
      app: portal-terminal
  template:
    metadata:
      labels:
        app: portal-terminal
    spec:
      containers:
      - name: portal-terminal
        image: cr.yandex/crp7i0e7br8dlil8465r/portal-terminal:latest
        ports:
        - containerPort: 8000
        env:
        - name: DB_HOST
          valueFrom:
            secretKeyRef:
              name: portal-secrets
              key: db-host
        # ... остальные переменные окружения
```

## Переменные окружения

Перед запуском контейнера убедитесь, что настроены следующие переменные окружения (через `.env` файл или другим способом):

- `DB_NAME` - имя базы данных PostgreSQL
- `DB_USER` - пользователь базы данных
- `DB_PASSWORD` - пароль базы данных
- `DB_HOST` - хост базы данных
- `DB_PORT` - порт базы данных (по умолчанию 5432)
- `SECRET_KEY` - секретный ключ Django
- `DEBUG` - режим отладки (True/False)
- `ALLOWED_HOSTS` - разрешенные хосты (разделенные запятыми)
- `REDIS_HOST` - хост Redis
- `REDIS_PORT` - порт Redis (по умолчанию 6379)
- `MODBUS_HOST` - хост Modbus (опционально)
- `MODBUS_PORT` - порт Modbus (опционально, по умолчанию 502)

Полный список переменных можно найти в файле `config/settings.py`.

## Особенности образа

- **Базовый образ**: `python:3.12-slim`
- **Порт**: 8000
- **Healthcheck**: встроен, проверяет доступность `/admin/login/`
- **Автоматические миграции**: выполняются при запуске контейнера
- **Создание суперпользователя**: автоматически создается пользователь `portal/portal`
- **Статические файлы**: собираются автоматически при запуске
- **Сервер**: Daphne (ASGI) для поддержки WebSocket

## Отладка

### Просмотр логов контейнера

```bash
docker logs -f portal-terminal
```

### Подключение к контейнеру

```bash
docker exec -it portal-terminal /bin/bash
```

### Проверка healthcheck

```bash
docker inspect --format='{{.State.Health.Status}}' portal-terminal
```

## CI/CD интеграция

Для автоматизации сборки и публикации можно использовать:

- **GitLab CI/CD**
- **GitHub Actions**
- **Yandex Cloud CI/CD**
- **Jenkins**

Пример для GitHub Actions (`.github/workflows/deploy.yml`):

```yaml
name: Build and Push to YCR

on:
  push:
    branches: [ main, master ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure Docker for YCR
      run: |
        yc container registry configure-docker
    
    - name: Build and push
      run: |
        REGISTRY_ID="crp7i0e7br8dlil8465r"
        IMAGE_NAME="portal-terminal"
        TAG=${GITHUB_SHA::7}
        docker build -t cr.yandex/${REGISTRY_ID}/${IMAGE_NAME}:${TAG} .
        docker push cr.yandex/${REGISTRY_ID}/${IMAGE_NAME}:${TAG}
      env:
        YC_TOKEN: ${{ secrets.YC_TOKEN }}
```

## Безопасность

1. **Не публикуйте `.env` файлы** в репозиторий
2. **Используйте секреты** для хранения чувствительных данных (например, через Yandex Lockbox)
3. **Регулярно обновляйте** базовый образ и зависимости
4. **Сканируйте образы** на уязвимости перед развертыванием
5. **Используйте специфичные теги** вместо `latest` в production

## Поддержка

При возникновении проблем:
1. Проверьте логи контейнера
2. Убедитесь, что переменные окружения настроены правильно
3. Проверьте сетевое соединение с базой данных и Redis
4. Убедитесь, что порт 8000 не занят







