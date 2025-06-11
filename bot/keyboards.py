from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from django.conf import settings
from django.contrib.auth.models import User

# Главное меню
main_markup = InlineKeyboardMarkup()
btn1 = InlineKeyboardButton("🛒 Каталог товаров", callback_data="catalog")
btn3 = InlineKeyboardButton("🛡️ Гарантия", callback_data="warranty_main_menu")
main_markup.add(btn1).add(btn3)

# Клавиатура для возврата в главное меню
back_to_main_markup = InlineKeyboardMarkup()
back_btn = InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_main")
back_to_main_markup.add(back_btn)

# Функция для создания клавиатуры с кнопкой назад
def get_back_markup(callback_data):
    markup = InlineKeyboardMarkup()
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data=callback_data)
    markup.add(back_btn)
    return markup

# Клавиатура для товара без кнопки расширенной гарантии
def get_product_menu_markup(product_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❓ FAQ", callback_data=f"faq_{product_id}"))
    markup.add(InlineKeyboardButton("🛡️ Гарантия", callback_data=f"warranty_{product_id}"))
    markup.add(InlineKeyboardButton("📞 Поддержка", callback_data=f"support_{product_id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"category_{product_id}"))
    return markup

# Клавиатура для активации расширенной гарантии
def get_warranty_markup_with_extended(product_id, has_extended_warranty=False):
    markup = InlineKeyboardMarkup()
    if not has_extended_warranty:
        markup.add(InlineKeyboardButton("✅ Активировать расширенную гарантию", callback_data=f"activate_warranty_{product_id}"))
    
    # Добавляем дополнительные кнопки
    markup.add(InlineKeyboardButton("📋 Условия гарантии", callback_data="warranty_conditions"))
    markup.add(InlineKeyboardButton("🛠️ Обратиться по гарантии", callback_data="warranty_cases"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{product_id}"))
    return markup

# Клавиатура для подтверждения отправки скриншота
def get_screenshot_markup(product_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_warranty_{product_id}"))
    return markup

def get_main_markup(user_id: int) -> ReplyKeyboardMarkup:
    """Создает главное меню с учетом роли пользователя"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📱 Каталог товаров")
    markup.row("🛡️ Гарантия", "🔧 Гарантийный случай")
    if User.objects.get(telegram_id=user_id).is_admin:
        markup.row("🔧 Админ-панель")
    return markup

def get_warranty_main_menu_markup(has_active_warranties=False):
    """Создает клавиатуру главного меню гарантии"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Условия гарантии", callback_data="warranty_conditions"))
    markup.add(InlineKeyboardButton("✅ Активировать расширенную гарантию", callback_data="catalog"))
    if has_active_warranties:
        markup.add(InlineKeyboardButton("🛡️ Мои гарантии", callback_data="my_warranties"))
    markup.add(InlineKeyboardButton("🛠️ Обратиться по гарантии", callback_data="warranty_cases"))
    markup.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
    return markup
