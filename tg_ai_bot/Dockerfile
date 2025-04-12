# Используем официальный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app


COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь текущий каталог в контейнер


# Указываем команду для запуска приложения
CMD ["python3", "-u", "main.py"] 