import logging
import telebot

from django.conf import settings

commands = settings.BOT_COMMANDS

# Проверяем что BOT_TOKEN установлен
if not getattr(settings, 'BOT_TOKEN', None):
    logging.error("BOT_TOKEN is not set in settings!")
    bot = None
else:
bot = telebot.TeleBot(
    settings.BOT_TOKEN,
    threaded=False,
    skip_pending=True,
    num_threads=1,  # Ограничиваем количество потоков для webhook
)

    try:
        bot.set_my_commands(commands)
    except Exception as e:
        logging.warning(f"Failed to set bot commands at startup: {e}")

    try:
        me = bot.get_me()
        logging.info(f'@{me.username} started')
    except Exception as e:
        logging.warning(f"Failed to fetch bot info at startup: {e}")

logger = telebot.logger
logger.setLevel(logging.INFO)

logging.basicConfig(level=logging.INFO, filename="ai_log.log", filemode="w")