import json
import html

def format_object_for_telegram(data, max_length=4000):
    """
    Преобразует объект Python (dict, list, etc.) в HTML-форматированную строку
    для Telegram, разбивая на части при необходимости.

    Args:
        data: Объект для форматирования.
        max_length (int): Максимальная длина одного сообщения Telegram (по умолчанию 4000).

    Returns:
        list[str]: Список строк, каждая из которых готова к отправке
                   в Telegram (в формате HTML).
    """
    try:
        # Используем json.dumps для красивого форматирования с отступами
        # ensure_ascii=False важен для корректного отображения кириллицы
        pretty_text = json.dumps(data, indent=4, ensure_ascii=False, sort_keys=True)
    except TypeError:
        # Если объект не сериализуется в JSON, используем repr
        pretty_text = repr(data)

    # Экранируем HTML-спецсимволы
    escaped_text = html.escape(pretty_text)

    # Базовая длина тегов <pre><code>...</code></pre>
    tags_len = len("<pre><code>") + len("</code></pre>")
    allowed_text_len = max_length - tags_len

    if allowed_text_len <= 0:
        print("Warning: max_length is too small to fit even the HTML tags.")
        return []

    # Проверяем, помещается ли все сообщение целиком
    if len(escaped_text) <= allowed_text_len:
        return [f"<pre><code>{escaped_text}</code></pre>"]

    # Разбиваем текст на части
    messages = []
    lines = escaped_text.split('\n')
    current_chunk = ""

    for line in lines:
        line_len_with_newline = len(line) + (1 if current_chunk else 0)

        if len(current_chunk) + line_len_with_newline <= allowed_text_len:
            if current_chunk:
                current_chunk += "\n"
            current_chunk += line
        else:
            if current_chunk:
                messages.append(f"<pre><code>{current_chunk}</code></pre>")
            
            if len(line) <= allowed_text_len:
                 current_chunk = line
            else:
                 print(f"Warning: Single line is too long ({len(line)} chars), splitting harshly.")
                 for i in range(0, len(line), allowed_text_len):
                     sub_line = line[i:i+allowed_text_len]
                     messages.append(f"<pre><code>{sub_line}</code></pre>")
                 current_chunk = "" 

    if current_chunk:
        messages.append(f"<pre><code>{current_chunk}</code></pre>")

    return messages 