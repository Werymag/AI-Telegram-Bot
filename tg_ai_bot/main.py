import asyncio
from telegram.constants import ParseMode
import time
import ollama
from bot_config import BotConfig
from helpers import  load_message_history, append_message_to_history
import os
import logging
import re 
import random
from telegram import Message

os.makedirs('data/logs', exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=f'data/logs/bot_{time.strftime("%Y-%m-%d")}.log')

# Загрузка конфигурации из JSON файла
logging.info("Приложение запущено!")

# Создаем папку для истории, если она не существует
os.makedirs('data/history', exist_ok=True)
path_to_config = 'data/configs/config.json'
history_file = 'data/history/message_history.json'

# Получаем адрес Ollama из переменной окружения,
# если она не задана, используем значение по умолчанию
ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
# Создаем клиента Ollama с указанным хостом
ollama_client = ollama.Client(host=ollama_host)

async def main(path_to_config):
    config = BotConfig(path_to_config)
    await config.initialize_bot()
    config.load_model_and_prompt()   
    logging.info("Бот инициализирован.")

    # Загрузка последних 200 сообщений из истории
    initial_messages = load_message_history(history_file, max_messages=200)

    await bot_loop(config, initial_messages)


async def bot_loop(config, initial_messages):
    logging.info("Бот начал прослушивание сообщений...")
    messages = initial_messages # Используем загруженные сообщения
    last_message_time = time.time()
    updates_counter = 0;
    next_random_number = 20;
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

            # Обрабатываем команды
            if len(new_messages) > 0:
                commands = [message for message in new_messages if message['is_command']]
                if commands:                
                    await process_commands(commands, config)                  

            # Проверяем, обращено ли сообщение к боту
            messages_to_bot = [message for message in new_messages if (message['is_bot_mention'] or message['is_reply_to_bot']) and not message['is_command']]
            if len(messages_to_bot) > 0:
                logging.info(f"Обнаружено {len(messages_to_bot)} сообщений непосредственно для бота.")
                await questions_for_bot(messages_to_bot, messages, config)
           
            # Проверяем, прошла ли минута с последнего сообщения и набралось 30 сообщений
            if updates_counter > next_random_number:
                logging.info(f"Накопилось {updates_counter} сообщений и прошло >= 60 сек. Запуск анализа диалога.")
                await analyze_and_send_response(messages, config)
                updates_counter = 0; # Сбрасываем счетчик после анализа
                next_random_number = random.randint(5, 40);

            # Очистка истории сообщений (без сохранения всего списка)
            if time.time() - last_message_time >= 1800: # 30 минут
                logging.info("Начало очистки старой истории сообщений...")
                original_user_history_counts = {user: len(hist) for user, hist in config.users_conversation_history.items()}
                users_to_clear = list(config.users_conversation_history.keys())
                for user in users_to_clear:
                    user_conversation_history = config.users_conversation_history[user]
                    if len(user_conversation_history) > 100:
                        config.users_conversation_history[user] = user_conversation_history[-100:]
                        logging.info(f"История пользователя {user} сокращена с {original_user_history_counts[user]} до {len(config.users_conversation_history[user])}.")

            if len(messages) > 200:
                original_len = len(messages)
                messages = messages[-200:]
                logging.info(f"Общая история сообщений в памяти сокращена с {original_len} до {len(messages)}.")

                updates_counter = 0;
                last_message_time = time.time() # Обновляем время, чтобы не чистить сразу снова
              
            # Небольшая пауза перед следующей проверкой
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"Неперехваченная ошибка в главном цикле echo_messages: {e}", exc_info=True)
            await asyncio.sleep(5) # Пауза при ошибке


async def get_updates(config):
    user_messages = []
    updates = []
    offset = config.last_update_id + 1 if config.last_update_id != -1 else None
    try:
        updates = await config.bot.get_updates(offset=offset, limit=50, timeout=10)

        for update in updates:
            # Проверяем, есть ли сообщение в обновлении
            if update.message: # Проверяем наличие message в принципе
                user = update.message.from_user.username or update.message.from_user.first_name
                text = update.message.text or "" # Используем пустую строку, если текста нет
                chat_id = update.message.chat.id
                message_id = update.message.message_id # ID текущего сообщения
                is_command = text.startswith('/')

                is_mention = f"@{config.bot_username}" in text if text else False
                is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.username == config.bot_username

                reply_to_message_id = None
                reply_to_message_text = None


                # Если сообщение является ответом или упоминанием бота, то получаем текст из оригинала
                if is_reply:
                    reply_to_message_id = update.message.reply_to_message.message_id
                    # Получаем текст из оригинала, если он есть
                    if update.message.reply_to_message.text:
                        reply_to_message_text = update.message.reply_to_message.text
                    elif update.message.reply_to_message.caption:
                        reply_to_message_text = f"Фото/Видео: {update.message.reply_to_message.caption or '(без подписи)'}"
                    elif update.message.reply_to_message.sticker:
                        reply_to_message_text = f"Стикер ({update.message.reply_to_message.sticker.emoji or '?'})"
                    else:
                        reply_to_message_text = "(Сообщение без текста)" # Заглушка для других типов

                user_message = {
                    'user': user,
                    'message': text,
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'is_command': is_command,
                    'is_bot_mention': is_mention,
                    'is_reply_to_bot': is_reply,
                    'reply_to_message_id': reply_to_message_id,
                    'reply_to_message_text': reply_to_message_text
                }

                # Добавляем сообщение только если есть текст или это команда (или в будущем другие условия)
                if text:
                    user_messages.append(user_message)
                    # Дописываем каждое сообщение в историю (если нужно для анализа)
                    append_message_to_history(user_message, history_file)
                    logging.info(f"[{chat_id}] {user}: {text[:50]}...")

            else:
                logging.debug(f"Получено обновление без сообщения (id={update.update_id})")

    except Exception as e:
        logging.error(f"Ошибка при получении обновлений (get_updates): {e}", exc_info=True)

    if updates:
        new_last_update_id = updates[-1].update_id
        if new_last_update_id != config.last_update_id:
                config.last_update_id = new_last_update_id
                logging.debug(f"Последний update_id обновлен: {config.last_update_id}")


    return user_messages


async def questions_for_bot(messages_to_bot, messages, config):
    for user_message_to_bot in messages_to_bot:
        user = user_message_to_bot['user']
        chat_id = user_message_to_bot['chat_id']
        message_text = user_message_to_bot['message']
        original_message_id = user_message_to_bot['message_id']
       

        logging.info(f"Обработка сообщения для бота от {user} (msg_id: {original_message_id}) в чате {chat_id}: \"{message_text[:50]}...\"")

        placeholder_message = None
        try:
            # Отправляем "Думаю..." в ответ на исходное сообщение
            placeholder_message = await config.bot.send_message(
                chat_id=chat_id,
                text="Думаю...",
                reply_to_message_id=original_message_id,
                disable_notification=True
            )
            logging.info(f"Отправлено сообщение-заглушка (ID: {placeholder_message.message_id}) для {user} в ответ на {original_message_id}")


            # Если пользователь не встречался в диалоге, то добавляем его в историю сообщений
            if user not in config.users_conversation_history:
                config.users_conversation_history[user] = []
                logging.info(f"Создана история для нового пользователя: {user}")

            # Добавляем исходное сообщение пользователя в его историю
            config.users_conversation_history[user].append({
                        "role": "user",
                        "content": message_text
                        })
            logging.debug(f"Сообщение от {user} (msg_id: {original_message_id}) добавлено в его историю.")

            # Отправляем запрос с историей сообщений
            logging.info(f"Подготовка и отправка запроса к ИИ (Ollama) для {user}...")

            ollama_messages = []

            # Добавляем диалог в список сообщений для ИИ
            dialog = "\n".join([f"{msg['user']}: {msg['message']}" for msg in messages if msg.get('message') and msg.get('is_command') == False ]) # Используем .get для безопасности
            system_prompt = (f"{config.bot_prompt}{dialog}")
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
  
            # Экранируем символы Markdown V2 в ответе ИИ
            ai_response_content = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', ai_response_content)
            
            # Редактируем сообщение-заглушку
            logging.info(f"Редактирование сообщения {placeholder_message.message_id} с ответом ИИ для {user}.")
            await config.bot.edit_message_text(
                chat_id=chat_id,
                message_id=placeholder_message.message_id,
                text=ai_response_content,
                parse_mode=ParseMode.MARKDOWN_V2 # Используем Markdown для цитаты
            )
            logging.info(f"Сообщение {placeholder_message.message_id} успешно отредактировано для {user}.")

        except Exception as e:
            logging.error(f"Ошибка при обработке сообщения для {user} (исходное msg_id: {original_message_id}) в чате {chat_id}: {e}", exc_info=True)
            error_text = "Извините, произошла ошибка при обработке вашего сообщения."
            # Если была ошибка ДО отправки ответа, пытаемся отредактировать заглушку сообщением об ошибке
            await config.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=placeholder_message.message_id,
                        text=error_text
                )


async def analyze_and_send_response(messages, config):
    if not messages:
        logging.warning("Попытка анализа пустого списка сообщений.")
        return

    chat_id = messages[-1]['chat_id'] # Предполагаем, что все сообщения из одного чата
    logging.info(f"Анализ диалога для чата {chat_id}. Количество сообщений: {len(messages)}.")

    placeholder_message = None
    try:
        # Фильтруем сообщения, чтобы оставить только те, у которых есть текст
        valid_messages = [msg for msg in messages if msg.get('message') and isinstance(msg.get('message'), str)]
        if not valid_messages:    
             return
         
         # Отправляем "Анализирую..."
        placeholder_message = await config.bot.send_message(
            chat_id=chat_id,
            text="Анализирую диалог...",
            disable_notification=True
        )
        logging.info(f"Отправлено сообщение-заглушка для анализа (ID: {placeholder_message.message_id}) в чат {chat_id}")

        ollama_messages = []

        dialog = "\n".join([f"{msg['user']}: {msg['message']}" for msg in valid_messages])

        system_prompt = (f"{config.bot_prompt}.\n {config.bot_analysis_prompt}"
                        f"Далее идёт диалог для анализа: {dialog}"
        )
        
        ollama_messages.append({
            "role": "system",
            "content": system_prompt
            })



        logging.info(f"Отправка запроса на анализ диалога в Ollama для чата {chat_id}...")
        response = ollama_client.chat(
            model=config.model_name,
            messages=ollama_messages,
            stream=False
        )

        # Удаляем текст "<think>...</think>" из ответа
        ai_response_content = re.sub(r'<think>.*?</think>', '', response['message']['content'], flags=re.DOTALL).strip()

        # Экранируем символы Markdown V2 в ответе ИИ
        ai_response_content = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', ai_response_content)    

        logging.info(f"Получен результат анализа от ИИ для чата {chat_id}: \"{ai_response_content[:50]}...\"")

        # Редактируем сообщение-заглушку
        logging.info(f"Редактирование сообщения {placeholder_message.message_id} с результатом анализа для чата {chat_id}.")
        await config.bot.edit_message_text(
            chat_id=chat_id,
            message_id=placeholder_message.message_id,
            text=ai_response_content,
            parse_mode=ParseMode.MARKDOWN_V2 
        )
        logging.info(f"Сообщение {placeholder_message.message_id} успешно отредактировано с результатом анализа для чата {chat_id}.")


    except Exception as e:
        logging.error(f"Ошибка при анализе диалога для чата {chat_id}: {e}", exc_info=True)
      
        error_text = "Извините, произошла ошибка при анализе диалога."
         
        await config.bot.edit_message_text(
            chat_id=chat_id,
            message_id=placeholder_message.message_id,
            text=error_text
        )


async def process_commands(commands, config):
    logging.info(f"Обработка {len(commands)} команд...")
    for command_message in commands:
        user = command_message['user']
        chat_id = command_message['chat_id']
        command_text = re.sub(r'@{config.bot_username}\s*', '', command_message['message']) # Удаляем имя бота из команды
        logging.info(f"Получена команда '{command_text}' от {user} в чате {chat_id}")

        response_messages = []
   
        try:       
            if command_text.startswith('/bot_show'):
                response_messages.append(str(ollama_client.show(model=config.model_name)))                
            elif command_text.startswith('/bot_ps'):
                response_messages.append(str(ollama_client.ps()))            
            elif command_text.startswith('/bot_list'):
                response_messages.append(str(ollama_client.list()))             
            elif command_text.startswith('/bot_system_prompt'):
                response_messages.append(config.bot_prompt)            
            elif command_text.startswith('/bot_analysis_prompt'):
                response_messages.append(config.bot_analysis_prompt)  
            elif command_text.startswith('/bot_current_model'):
                response_messages.append(config.model_name)
            elif command_text.startswith('/bot_set_system_prompt'):                
                new_prompt = command_text.split(' ', 1)[1]
                config.bot_prompt = new_prompt
                config.save_model_and_prompt()  
                response_messages.append(f"Системный промт успешно изменен.")                
            elif command_text.startswith('/bot_set_analysis_prompt'):                
                new_prompt = command_text.split(' ', 1)[1]
                config.bot_analysis_prompt = new_prompt
                config.save_model_and_prompt()  
                response_messages.append(f"Промт анализа диалога успешно изменен.")               
            elif command_text.startswith('/bot_set_model'):             
                new_model = command_text.split(' ', 1)[1]
                config.model_name = new_model
                ollama_client.pull(model=config.model_name)
                config.save_model_and_prompt()  
                response_messages.append(f"Модель успешно изменена на {config.model_name}.")       
            elif command_text.startswith('/bot_delete_model'):             
                model_name = command_text.split(' ', 1)[1]
                ollama_client.delete(model=model_name)
                response_messages.append(f"Модель {model_name} успешно удалена.")
            else:
                help_text = "Список команд:\n"
                help_text += "/bot_help - показать список команд\n"
                help_text += "/bot_show - показать информацию о модели\n"
                help_text += "/bot_ps - показать список запущенных моделей\n"
                help_text += "/bot_list - показать список доступных моделей\n"
                help_text += "/bot_system_prompt - показать системный промт\n"
                help_text += "/bot_analysis_prompt - показать промт анализа диалога\n"
                help_text += "/bot_set_system_prompt [новый промт] - изменить системный промт\n"
                help_text += "/bot_set_analysis_prompt [новый промт] - изменить промт анализа\n"
                help_text += "/bot_set_model [имя модели] - изменить модель ИИ\n"
                response_messages.append(help_text)

            # Отправляем все подготовленные сообщения
            for msg_part in response_messages:
                msg_part = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', msg_part)    
                await config.bot.send_message(
                    chat_id=chat_id,
                    text=msg_part,
                    parse_mode=ParseMode.MARKDOWN_V2, # Используем HTML для <pre><code>
                    disable_notification=True
                )
            logging.info(f"Ответ на команду '{command_text}' ({len(response_messages)} частей) отправлен {user}.")

        except Exception as e:
            logging.error(f"Ошибка при обработке команды '{command_text}' от {user}: {e}", exc_info=True)
            try:
                await config.bot.send_message(
                    chat_id=chat_id,
                    text=f"Произошла ошибка при выполнении команды: {e}",
                    disable_notification=True
                )
            except Exception as send_error:
                logging.error(f"Не удалось отправить сообщение об ошибке команды пользователю {user}: {send_error}")


# Запуск основной логики.
if __name__ == "__main__":
    try:
        asyncio.run(main(path_to_config))
    except Exception as global_error:
        logging.critical(f"Критическая неперехваченная ошибка в __main__: {global_error}", exc_info=True)
    finally:
        logging.info("Приложение завершено!")
