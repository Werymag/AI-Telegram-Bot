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
        token = os.environ.get('TELEGRAM_TOKEN')
        model_name = os.environ.get('MODEL_NAME', 'mistral-small3.1')
        self.model_name = model_name
        self.tg_token = token
        trequest = HTTPXRequest(connection_pool_size=20)
        self.bot = telegram.Bot(self.tg_token, request=trequest)
        bot_info = await self.bot.get_me()
        self.bot_username = bot_info.username 
        self.bot_prompt = f"Ты телеграм бот с именем \"Кот Советчик\" с никнеймом в чате {self.bot_username}, помогающий разрешать споры, анализировать диалоги и улучшать настроение. "\
                        "Ты отвечаешь на вопросы пользователей или отвечаешь, когда тебя упоминают в чате Telegram. "\
                        "Не цитируй сообщения и диалог в своем ответе если тебя не просят об этом. "\
                        "Оформляй ответы с учётом вставки в чат Telegram и разметкой в стиле Markdown v2. Обязательно проверяй закрытие всех тегов Markdown в ответе. Отвечай только на русском языке."\
                        "Не пиши иероглифы в ответе."\
                        "При ответе учитывай контекст представленного далее диалога нескольких пользователей в чате. Диалог представляет из себя список сообщений, где сначала написаны никнеймы, затем, через двоеточие, их сообщения. "\
                        "Далее идёт диалог в чате пользователей коотрый надо учитывать при ответе:\n"
        self.bot_analysis_prompt = "Выскажи своё мнение о обсуждаемом вопросе, если это уместно. Если диалог не спор, просто поучавствуй в разговоре или пошути. Отвечай кратко."                



    def save_model_and_prompt(self):
        """Сохраняет имя модели и промт в файл, создавая файл, если он не существует."""
        data = {
            'model_name': self.model_name,
            'bot_prompt': self.bot_prompt,
            'bot_analysis_prompt': self.bot_analysis_prompt
        }
        # Создаем файл, если он не существует
        os.makedirs(os.path.dirname(self.path_to_config), exist_ok=True)
        with open(self.path_to_config, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_model_and_prompt(self):
        """Загружает имя модели и промт из файла."""
        if os.path.exists(self.path_to_config):
            with open(self.path_to_config, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.model_name = data.get('model_name', self.model_name)
                self.bot_prompt = data.get('bot_prompt', self.bot_prompt)
                self.bot_analysis_prompt = data.get('bot_analysis_prompt', self.bot_analysis_prompt)

            