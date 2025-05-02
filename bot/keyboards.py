from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# Главное меню
main_markup = InlineKeyboardMarkup()
btn1 = InlineKeyboardButton("🛒 Каталог товаров", callback_data="menu")
btn2 = InlineKeyboardButton("📞 Поддержка", callback_data="support_menu")
main_markup.add(btn1).add(btn2)

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
