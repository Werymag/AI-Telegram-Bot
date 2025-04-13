#!/bin/bash

# Создаем папки внутри ./data, если они не существуют (-p игнорирует ошибку, если папки есть)
# mkdir -p ./data/logs
# mkdir -p ./data/configs
# mkdir -p ./data/history

docker compose down
# Запускаем docker-compose с пересборкой сервиса app и в фоновом режиме
docker compose up -d --build app