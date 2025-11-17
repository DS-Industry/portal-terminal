#!/bin/bash

# Скрипт для сборки и публикации образа в Yandex Container Registry
# Registry ID: crp7i0e7br8dlil8465r

set -e

# Конфигурация
REGISTRY_ID="crp7i0e7br8dlil8465r"
IMAGE_NAME="terminal-backend"
REGISTRY_HOST="cr.yandex"
FULL_IMAGE_NAME="${REGISTRY_HOST}/${REGISTRY_ID}/${IMAGE_NAME}"

# Получаем тег (версию) из аргумента или используем git commit hash
if [ -z "$1" ]; then
    TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
else
    TAG="$1"
fi

FULL_IMAGE_TAG="${FULL_IMAGE_NAME}:${TAG}"
LATEST_TAG="${FULL_IMAGE_NAME}:latest"

echo "========================================="
echo "Building Docker image for Yandex Container Registry"
echo "========================================="
echo "Registry: ${REGISTRY_HOST}"
echo "Registry ID: ${REGISTRY_ID}"
echo "Image: ${IMAGE_NAME}"
echo "Tag: ${TAG}"
echo "Full image name: ${FULL_IMAGE_TAG}"
echo "========================================="

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Проверяем авторизацию в YCR (опционально)
echo ""
echo "Checking Yandex Cloud authentication..."
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Собираем образ
echo ""
echo "Building Docker image..."
docker build -t "${FULL_IMAGE_TAG}" -t "${LATEST_TAG}" .

if [ $? -ne 0 ]; then
    echo "Error: Docker build failed"
    exit 1
fi

echo ""
echo "Build completed successfully!"
echo ""

# Запрашиваем подтверждение для публикации
read -p "Do you want to push the image to Yandex Container Registry? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Pushing image to Yandex Container Registry..."
    
    # Авторизация в YCR (если требуется)
    # Раскомментируйте следующую строку и выполните команду один раз:
    # yc container registry configure-docker
    
    # Публикуем образ с указанным тегом
    docker push "${FULL_IMAGE_TAG}"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "Pushing latest tag..."
        docker push "${LATEST_TAG}"
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "========================================="
            echo "✓ Image successfully pushed to Yandex Container Registry"
            echo "========================================="
            echo "Image: ${FULL_IMAGE_TAG}"
            echo "Latest: ${LATEST_TAG}"
            echo ""
            echo "To pull the image, use:"
            echo "  docker pull ${FULL_IMAGE_TAG}"
            echo ""
            echo "To run the container:"
            echo "  docker run -p 8000:8000 --env-file .env ${FULL_IMAGE_TAG}"
        else
            echo "Warning: Failed to push latest tag"
            exit 1
        fi
    else
        echo "Error: Failed to push image to registry"
        exit 1
    fi
else
    echo ""
    echo "Image built locally but not pushed."
    echo "To push manually, run:"
    echo "  docker push ${FULL_IMAGE_TAG}"
    echo "  docker push ${LATEST_TAG}"
fi





