#!/bin/bash

# Создаем папку logs, если она не существует (-p игнорирует ошибку, если папка есть)
mkdir -p ./logs

# Запускаем docker-compose с пересборкой сервиса app и в фоновом режиме
docker-compose up --build app