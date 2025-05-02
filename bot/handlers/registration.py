from bot.models import User
from bot import bot


def start_registration(message):
    from bot.handlers.common import menu_m
    """ Функция для регистрации пользователей """
    user_id = message.from_user.id
    user = User.objects.filter(telegram_id=user_id)
    if user.exists():
        menu_m(message)
    else:
        User.objects.create(
            telegram_id=user_id,
            user_name=message.from_user.first_name
        )
        menu_m(message)
        
