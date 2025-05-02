import os
import django
import dotenv

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dd.settings')
django.setup()

# Загрузка переменных окружения
dotenv.load_dotenv()

# Импорт бота после настройки Django
from bot import bot
from bot.handlers import *  # Импортируем обработчики

if __name__ == '__main__':
    print("Запуск бота в режиме поллинга...")
    bot.remove_webhook()
    bot.infinity_polling() 