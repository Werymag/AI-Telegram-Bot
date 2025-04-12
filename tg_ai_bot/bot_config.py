from telegram.request import HTTPXRequest
import telegram
import json
import os

class BotConfig:
    def __init__(self, path_to_config):
        self.path_to_config = path_to_config
        self.model_name = None    # Имя модели для использования
        self.tg_token = None
        self.bot_username = None  # Имя пользователя бота, будет установлено позже      
        self.bot = None 
        self.last_update_id = -1;
        self.users_conversation_history = {}
        self.bot_prompt = None

    async def initialize_bot(self):
        token = os.environ.get('TELEGRAM_TOKEN', '5783330360:AAGd5cok3mhB0_iAIF6mP4FLM4Nf5lpiZC0')
        model_name = os.environ.get('MODEL_NAME', 'deepseek-r1:14b')
        self.model_name = model_name
        self.tg_token = token
        trequest = HTTPXRequest(connection_pool_size=20)
        self.bot = telegram.Bot(self.tg_token, request=trequest)
        bot_info = await self.bot.get_me()
        self.bot_username = bot_info.username 
        self.bot_prompt = f"Ты телеграм бот с именем \"Кот Советчик\" с никнеймом в чате {self.bot_username}, , помогающий разрешать споры, анализировать диалоги и улучшать настроение. "\
                        "Ты отвечаешь на вопросы пользователей или отвечаешь, когда тебя упоминают в диалоге. "\
                        "При ответе учитывай контекст диалога в чате. Диалог представляет из себя список сообщений, где сначала написаны никнеймы, затем их сообщения. "\
                        "Не цитируй сообщения и диалог в своем ответе если тебя не просят об этом. "\
                        "Оформляй ответы с учётом вставки в чат Telegram и разметкой в стиле MARKDOWN. "