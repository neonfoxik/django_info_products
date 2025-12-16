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
    print("Удаление webhook для использования поллинга...")
    bot.remove_webhook()
    print("Webhook удален. Запуск поллинга...")

    # Запуск бота с поллингом
    bot.polling(none_stop=True, interval=0) 