# Telegram AI Bot

Этот проект представляет собой Telegram-бота, интегрированного с языковой моделью через Ollama.

Данный проект написан с активным использованием ИИ-ассистенов и технических возможностей браузера Cursor AI.

## Структура проекта

- `tg_ai_bot/`: Основной код бота.
  - `main.py`: Главный файл бота.
  - `bot_config.py`: Файл конфигурации бота.
  - `Dockerfile`: Инструкции для сборки Docker-образа бота.
  - `requirements.txt`: Зависимости Python.
- `docker-compose.yml`: Определяет сервисы Ollama и бота для запуска через Docker Compose.
- `run_tg_ai.sh`: Скрипт для удобного запуска проекта (создает директорию логов и запускает `docker-compose`).
- `.env`: Файл для переменных окружения, используемых `docker-compose.yml` (токен Telegram, имя модели Ollama).
- `logs/`: Директория для хранения логов.
- `.gitignore`: Файл для исключения файлов из Git.

## Запуск

1.  **Установите Docker и Docker Compose.**
2.  **Создайте файл `.env`** в корне проекта со следующим содержимым:
    ```env
    TELEGRAM_TOKEN=ВАШ_ТЕЛЕГРАМ_ТОКЕН
    MODEL_NAME=имя_модели_ollama # Например, llama3
    ```
    Замените `ВАШ_ТЕЛЕГРАМ_ТОКЕН` на токен вашего бота и `имя_модели_ollama` на имя модели, которую вы хотите использовать с Ollama (она будет скачана автоматически при первом запуске, если её нет).
3.  **Запустите скрипт:**
    ```bash
    ./run_tg_ai.sh
    ```
    Или выполните команды вручную:
    ```bash
    mkdir -p ./logs
    docker compose up --build -d # Опция -d для запуска в фоновом режиме
    ```
    При первом запуске может потребоваться время на скачивание образа Ollama и указанной модели.

4.  Бот и сервер Ollama будут запущены в Docker-контейнерах. Логи будут сохраняться в директорию `logs/`.

## Остановка

```bash
docker compose down
```

## Конфигурация

- Настройки бота (приветственное сообщение, лимиты и т.д.) находятся в `tg_ai_bot/bot_config.py`.
- Параметры запуска сервисов Docker (порты, тома, модель Ollama) настраиваются в `docker-compose.yml` и через файл `.env`. 
