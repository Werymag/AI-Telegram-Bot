import asyncio
from telegram.constants import ParseMode
import time
import ollama
from bot_config import BotConfig
import os
import logging
import re 
import random
# Загрузка конфигурации из JSON файла
path_to_config = 'config.json'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=f'logs/bot_{time.strftime("%Y-%m-%d")}.log')
logging.info("Приложение запущено!")

# Получаем адрес Ollama из переменной окружения,
# если она не задана, используем значение по умолчанию
ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
# Создаем клиента Ollama с указанным хостом
ollama_client = ollama.Client(host=ollama_host)

async def main(path_to_config):
    config = BotConfig(path_to_config)
    logging.info("Инициализация бота...")
    await config.initialize_bot()
    logging.info("Бот инициализирован.")
    await echo_messages(config)


async def echo_messages(config):
    logging.info("Бот начал прослушивание сообщений...")
    messages = []
    last_message_time = time.time()
    updates_counter = 0;
    while True:
        try:
            # Получаем новые сообщения
            logging.debug("Проверка новых сообщений...")
            new_messages = await get_updates(config)
            if new_messages:
                updates_counter += len(new_messages)
                last_message_time = time.time()
                messages.extend(new_messages)
                logging.info(f"Получено {len(new_messages)} новых сообщений. Общее количество необработанных: {updates_counter}")


            if len(new_messages) > 0:
                commands = [message for message in new_messages if message['text'].startswith('/')]
                if commands:                
                    await process_commands(commands, config)
                    

            # Проверяем, обращено ли сообщение к боту
            messages_to_bot = [message for message in new_messages if message['is_bot_mention'] or message['is_reply_to_bot']]
            if len(messages_to_bot) > 0:
                logging.info(f"Обнаружено {len(messages_to_bot)} сообщений непосредственно для бота.")
                await questions_for_bot(messages_to_bot, messages, config)

            # Проверяем, прошла ли минута с последнего сообщения и набралось 30 сообщений
            if updates_counter > random.randint(5, 40):
                logging.info(f"Накопилось {updates_counter} сообщений и прошло >= 60 сек. Запуск анализа диалога.")
                await analyze_and_send_response(messages, config)
                updates_counter = 0; # Сбрасываем счетчик после анализа

            # Очистка истории сообщений
            if time.time() - last_message_time >= 1800: # 30 минут                
                original_user_history_counts = {user: len(hist) for user, hist in config.users_conversation_history.items()}
                users_to_clear = list(config.users_conversation_history.keys())
                for user in users_to_clear:
                    user_conversation_history = config.users_conversation_history[user]
                    if len(user_conversation_history) > 100:
                        config.users_conversation_history[user] = user_conversation_history[-100:]
                        logging.info(f"История пользователя {user} сокращена с {original_user_history_counts[user]} до {len(config.users_conversation_history[user])}.")

                if len(messages) > 100:
                    original_len = len(messages)
                    messages = messages[-100:]
                    logging.info(f"Общая история сообщений сокращена с {original_len} до {len(messages)}.")

                updates_counter = 0;
                last_message_time = time.time() # Обновляем время, чтобы не чистить сразу снова
                
            # Небольшая пауза перед следующей проверкой
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"Неперехваченная ошибка в главном цикле echo_messages: {e}", exc_info=True)
            await asyncio.sleep(5) # Пауза при ошибке


async def get_updates(config):
    user_messages = []
    try:
        updates = []
        offset = config.last_update_id + 1 if config.last_update_id != -1 else None 
        updates = await config.bot.get_updates(offset=offset, limit=50, timeout=10)

        for update in updates:
            # Проверяем, есть ли сообщение в обновлении
            if update.message and update.message.text:
                user = update.message.from_user.username or update.message.from_user.first_name
                text = update.message.text
                chat_id = update.message.chat.id
                is_mention = f"@{config.bot_username}" in text if text else False
                is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.username == config.bot_username

                user_message = {
                    'user': user,
                    'message': text,
                    'chat_id': chat_id,
                    'is_bot_mention': is_mention,
                    'is_reply_to_bot': is_reply
                }
                user_messages.append(user_message)
                logging.info(f"[{chat_id}] {user}: {text[:50]}...")
            elif update.message:
                 logging.debug(f"Получено обновление с сообщением без текста (id={update.update_id})")
            else:
                 logging.debug(f"Получено обновление без сообщения (id={update.update_id})")

        if updates:
            new_last_update_id = updates[-1].update_id
            if new_last_update_id != config.last_update_id:
                 config.last_update_id = new_last_update_id
                 logging.debug(f"Последний update_id обновлен: {config.last_update_id}")

    except Exception as e:
        logging.error(f"Ошибка при получении обновлений (get_updates): {e}", exc_info=True)
        # Не возвращаем пустой список, чтобы не терять last_update_id при временной ошибке сети

    return user_messages


async def questions_for_bot(messages_to_bot, messages, config):
    for user_message_to_bot in messages_to_bot:
        user = user_message_to_bot['user']
        chat_id = user_message_to_bot['chat_id']
        message_text = user_message_to_bot['message']
        logging.info(f"Обработка сообщения для бота от {user} в чате {chat_id}: \"{message_text[:50]}...\"")
        try:
            # Если пользователь не встречался в диалоге, то добавляем его в историю сообщений
            if user not in config.users_conversation_history:
                config.users_conversation_history[user] = []
                logging.info(f"Создана история для нового пользователя: {user}")

            config.users_conversation_history[user].append({
                        "role": "user",
                        "content": message_text
                        })
            logging.debug(f"Сообщение от {user} добавлено в его историю.")

            # Отправляем запрос с историей сообщений
            logging.info(f"Подготовка и отправка запроса к ИИ (Ollama) для {user}...")

            ollama_messages = []

            # Добавляем диалог в список сообщений для ИИ
            dialog = "\n".join([f"{msg['user']}: {msg['message']}" for msg in messages if msg.get('message')]) # Используем .get для безопасности
            system_prompt = (f"{config.bot_prompt}.\nДалее идёт диалог между пользователями: {dialog}")
            ollama_messages.append({
                    "role": "system",
                    "content": system_prompt
                    })

            # Добавляем историю сообщений пользователя в список сообщений для ИИ (последние N)
            user_history_for_ollama = config.users_conversation_history[user][-20:] # Берем последние 20
            ollama_messages.extend(user_history_for_ollama)
            logging.debug(f"Сформировано {len(ollama_messages)} сообщений для Ollama ({len(user_history_for_ollama)} от {user}).")
            logging.info(f"Текст сообщений для Ollama, модель {config.model_name}: {ollama_messages}")
            
            
            response = ollama_client.chat(
                model=config.model_name,
                messages=ollama_messages,
                stream=False
            )            
            
            # Удаляем текст "<think>...</think>" из ответа
            ai_response_content = re.sub(r'<think>.*?</think>', '', response['message']['content'], flags=re.DOTALL).strip()
            
            logging.info(f"Получен ответ от ИИ для {user}: \"{ai_response_content[:50]}...\"")

            # Добавляем ответ ИИ в историю сообщений пользователя
            config.users_conversation_history[user].append({
                        "role": "assistant",
                        "content": ai_response_content
                        })
            logging.debug(f"Ответ ИИ добавлен в историю {user}.")

            # Отправляем ответ пользователю
            logging.info(f"Отправка ответа ИИ пользователю {user} в чат {chat_id}.")
            await config.bot.send_message(
                chat_id=chat_id,
                text=ai_response_content,
                parse_mode=ParseMode.HTML,
                disable_notification=True
            )
            logging.info(f"Ответ ИИ успешно отправлен {user}.")

        except Exception as e:
            logging.error(f"Ошибка при обработке личного сообщения для {user} в чате {chat_id}: {e}", exc_info=True)
            try:
                # Попытка уведомить пользователя об ошибке
                await config.bot.send_message(
                    chat_id=chat_id,
                    text="Извините, произошла ошибка при обработке вашего сообщения.",
                    disable_notification=True
                )
            except Exception as send_error:
                logging.error(f"Не удалось отправить сообщение об ошибке пользователю {user} в чат {chat_id}: {send_error}", exc_info=True)


async def analyze_and_send_response(messages, config):
    if not messages:
        logging.warning("Попытка анализа пустого списка сообщений.")
        return

    chat_id = messages[-1]['chat_id'] # Предполагаем, что все сообщения из одного чата
    logging.info(f"Анализ диалога для чата {chat_id}. Количество сообщений: {len(messages)}.")
    try:
        ollama_messages = []

        dialog = "\n".join([f"{msg['user']}: {msg['message']}" for msg in messages if msg.get('message')])

        if not dialog.strip():
             logging.warning(f"Диалог для анализа в чате {chat_id} пуст после фильтрации. Анализ отменен.")
             return

        system_prompt = (f"{config.bot_prompt}.\nВыскажи своё мнение о обсуждаемом вопросе, если это уместно. Если диалог не спор, просто поучавствуй в разговоре или пошути."
                        f"Далее идёт диалог для анализа: {dialog}"
        )
        ollama_messages.append({
            "role": "system",
            "content": system_prompt
            })

        ollama_messages.append({
                "role": "user",
                "content": "Сделай выводы о диалоге"
                })

        logging.info(f"Отправка запроса на анализ диалога в Ollama для чата {chat_id}...")
        response = ollama_client.chat(
            model=config.model_name,
            messages=ollama_messages,
            stream=False
        )
        
        # Удаляем текст "<think>...</think>" из ответа
        ai_response_content = re.sub(r'<think>.*?</think>', '', response['message']['content'], flags=re.DOTALL).strip()
        
        logging.info(f"Получен результат анализа от ИИ для чата {chat_id}: \"{ai_response_content[:50]}...\"")

        # Отправляем ответ в чат
        logging.info(f"Отправка результата анализа в чат {chat_id}.")
        await config.bot.send_message(
            chat_id=chat_id,
            text=ai_response_content,
            parse_mode=ParseMode.HTML,
            disable_notification=True
        )
        logging.info(f"Результат анализа успешно отправлен в чат {chat_id}.")

    except Exception as e:
        logging.error(f"Ошибка при анализе диалога для чата {chat_id}: {e}", exc_info=True)
        try:
            # Попытка уведомить чат об ошибке анализа
            await config.bot.send_message(
                chat_id=chat_id,
                text="Извините, произошла ошибка при анализе диалога.",
                disable_notification=True
            )
            logging.info(f"Сообщение об ошибке анализа отправлено в чат {chat_id}.")
        except Exception as send_error:
            logging.error(f"Не удалось отправить сообщение об ошибке анализа в чат {chat_id}: {send_error}", exc_info=True)


async def process_commands(commands, config):
    logging.info(f"Обработка {len(commands)} команд...")
    for command_message in commands:
        user = command_message['user']
        chat_id = command_message['chat_id']
        command_text = command_message['message']
        logging.info(f"Получена команда '{command_text}' от {user} в чате {chat_id}")
        
        try:
            if command_text.startswith('/bot_help'):
                response_text = "Список команд:\n"
                response_text += "/bot_show - показать информацию о модели\n"
                response_text += "/bot_ps - показать список запущенных моделей\n"
                response_text += "/bot_list - показать список доступных моделей\n"
                response_text += "/bot_pull - скачать модель\n"
                response_text += "/bot_push - загрузить модель\n"
                response_text += "/bot_system_prompt - показать системный промт\n"
                response_text += "/bot_set_system_prompt - изменить системный промт\n"
            elif command_text.startswith('/bot_show'):
                response_text = ollama_client.show(model=config.model_name)
            elif command_text.startswith('/bot_ps'):
                response_text = ollama_client.ps()
            elif command_text.startswith('/bot_list'):
                response_text = ollama_client.list()
            elif command_text.startswith('/bot_pull'):
                response_text = ollama_client.pull(model=config.model_name)
            elif command_text.startswith('/bot_push'):
                response_text = ollama_client.push(model=config.model_name)
            elif command_text.startswith('/bot_system_prompt'):
                response_text = config.bot_prompt
            elif command_text.startswith('/bot_set_system_prompt'):
                config.bot_prompt = command_text.split(' ')[1]
                response_text = f"Системный промт успешно изменен."
            elif command_text.startswith('/bot_set_model'):
                config.model_name = command_text.split(' ')[1]
                response_text = f"Модель успешно изменена на {config.model_name}."
            else:
                response_text = f"Команда '{command_text}' пока не поддерживается."

            await config.bot.send_message(
                chat_id=chat_id,
                text=response_text,
                disable_notification=True
            )
            logging.info(f"Ответ на команду '{command_text}' отправлен {user}.")
        except Exception as e:
            logging.error(f"Ошибка при обработке команды '{command_text}' от {user}: {e}", exc_info=True)


# Запуск основной логики.
if __name__ == "__main__":
    try:
        asyncio.run(main(path_to_config))
    except Exception as global_error:
        logging.critical(f"Критическая неперехваченная ошибка в __main__: {global_error}", exc_info=True)
    finally:
        logging.info("Приложение завершено!")
