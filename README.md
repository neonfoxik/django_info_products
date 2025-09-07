# TRANSPEED BOT

Официальный Telegram бот бренда TRANSPEED для поддержки клиентов и управления гарантийными случаями.

## 🚀 Возможности

## 🛠️ Установка и запуск

### Требования
- Python 3.8+
- Django 5.1+
- PostgreSQL/MySQL
- Telegram Bot Token

### Установка
```bash
# Клонирование репозитория
git clone <repository-url>
cd TRANSPEED_BOT

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл с вашими настройками

# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск бота
python bot_polling.py
```
