import json
import html
import os
import logging
from collections import deque

def append_message_to_history(message, history_file):
    """
    Дописывает одно сообщение в файл истории.
    Каждое сообщение сохраняется как отдельная JSON-строка.

    Args:
        message (dict): Словарь сообщения.
        history_file (str): Путь к файлу истории.
    """
    try:
        with open(history_file, 'a', encoding='utf-8') as f:
            json_string = json.dumps(message, ensure_ascii=False)
            f.write(json_string + '\n')
    except Exception as e:
        logging.error(f"Ошибка дозаписи сообщения в файл истории {history_file}: {e}", exc_info=True)

def load_message_history(history_file, max_messages=200):
    """
    Загружает последние N сообщений из файла истории.
    Каждая строка файла считается отдельным JSON-сообщением.

    Args:
        history_file (str): Путь к файлу истории.
        max_messages (int): Максимальное количество сообщений для загрузки.

    Returns:
        list: Список загруженных сообщений (от старых к новым) или пустой список при ошибке/отсутствии файла.
    """
    messages = []
    try:
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                # Используем deque для эффективного хранения последних N строк
                last_lines = deque(f, maxlen=max_messages)

            for i, line in enumerate(last_lines):
                try:
                    message = json.loads(line.strip())
                    messages.append(message)
                except json.JSONDecodeError:
                    # Логируем номер строки относительно прочитанных последних N
                    logging.warning(f"Ошибка декодирования JSON в строке {i+1}/{len(last_lines)} файла истории {history_file}. Строка пропущена: {line.strip()[:100]}...")
                except Exception as parse_error:
                    logging.error(f"Неизвестная ошибка при парсинге строки {i+1}/{len(last_lines)} из истории {history_file}: {parse_error}. Строка: {line.strip()[:100]}...", exc_info=True)

            logging.info(f"Загружено {len(messages)}/{len(last_lines)} последних сообщений из истории {history_file}.")
        else:
            logging.info(f"Файл истории {history_file} не найден, начинаем с пустой истории.")
    except Exception as e:
        logging.error(f"Не удалось загрузить историю сообщений из {history_file}: {e}. Начинаем с пустой истории.", exc_info=True)
    return messages

