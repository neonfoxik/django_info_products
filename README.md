# Django Info Products

Платформа для продажи информационных продуктов, созданная с использованием Django и интегрированная с Telegram-ботом.

## Функциональность

- Продажа информационных продуктов через Telegram бота
- Система управления контентом
- Интеграция с платежными системами
- Статистика продаж и аналитика

## Требования

См. файл requirements.txt для полного списка зависимостей.

## Установка

```bash
# Клонирование репозитория
git clone https://github.com/YOUR_USERNAME/django_info_products.git
cd django_info_products

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env  # И отредактируйте .env файл

# Применить миграции
python manage.py migrate

# Запуск сервера
python manage.py runserver
```

## Переменные окружения

Создайте файл .env со следующими переменными:
- BOT_TOKEN - Токен Telegram бота
- OPENAI_API_KEY - Ключ API OpenAI
- OWNER_ID - ID владельца бота в Telegram
- И другие необходимые переменные
