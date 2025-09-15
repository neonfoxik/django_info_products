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
btn2 = InlineKeyboardButton("📞 Поддержка", callback_data="help_main")
btn3 = InlineKeyboardButton("🛡️ Гарантия", callback_data="warranty_main_menu")
btn4 = InlineKeyboardButton("🎫 Получить промокод", callback_data="get_promocode")
main_markup.add(btn1).add(btn2).add(btn3).add(btn4)

# Клавиатура для выбора типа поддержки (устаревшая, заменена на get_support_platform_markup)
support_markup = InlineKeyboardMarkup()
support_ozon_btn = InlineKeyboardButton("🟠 Поддержка Озон", callback_data="support_ozon")
support_wb_btn = InlineKeyboardButton("🟣 Поддержка Вайлдберриз", callback_data="support_wildberries")
back_support_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
support_markup.add(support_ozon_btn).add(support_wb_btn).add(back_support_btn)

# Клавиатура для выбора платформы покупки
def get_platform_choice_markup(action_type, product_id=None):
    """Создает клавиатуру для выбора платформы покупки товара"""
    markup = InlineKeyboardMarkup()
    
    if product_id:
        ozon_btn = InlineKeyboardButton("🟠 Озон", callback_data=f"{action_type}_ozon_{product_id}")
        wb_btn = InlineKeyboardButton("🟣 Вайлдберриз", callback_data=f"{action_type}_wb_{product_id}")
    else:
        ozon_btn = InlineKeyboardButton("🟠 Озон", callback_data=f"{action_type}_ozon")
        wb_btn = InlineKeyboardButton("🟣 Вайлдберриз", callback_data=f"{action_type}_wb")
    
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    
    markup.add(ozon_btn).add(wb_btn).add(back_btn)
    return markup

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
    markup.add(InlineKeyboardButton("📖 Инструкция", callback_data=f"instructions_{product_id}"))
    markup.add(InlineKeyboardButton("❓ FAQ", callback_data=f"faq_{product_id}"))
    markup.add(InlineKeyboardButton("🛡️ Гарантия", callback_data=f"warranty_{product_id}"))
    #markup.add(InlineKeyboardButton("📞 Поддержка", callback_data=f"support_{product_id}"))
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
    markup.add(InlineKeyboardButton("✅ Активировать расширенную гарантию", callback_data="waranty_goods_fast"))
    if has_active_warranties:
        markup.add(InlineKeyboardButton("🛡️ Мои гарантии", callback_data="my_warranties"))
    markup.add(InlineKeyboardButton("🛠️ Обратиться по гарантии", callback_data="warranty_cases"))
    markup.add(InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main"))
    return markup

# Клавиатуры для системы поддержки

def get_support_platform_markup():
    """Создает клавиатуру для выбора платформы поддержки"""
    markup = InlineKeyboardMarkup()
    ozon_btn = InlineKeyboardButton("🟠 Поддержка Озон", callback_data="support_ozon")
    wb_btn = InlineKeyboardButton("🟣 Поддержка Вайлдберриз", callback_data="support_wildberries")
    my_btn = InlineKeyboardButton("🗂 Мои обращения", callback_data="support_my_tickets")
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    markup.add(ozon_btn).add(wb_btn).add(my_btn).add(back_btn)
    return markup

def get_close_ticket_markup():
    """Создает кнопку для закрытия обращения под сообщением админа"""
    markup = InlineKeyboardMarkup()
    close_btn = InlineKeyboardButton("✅ Спасибо, я получил ответ на свой вопрос", callback_data="close_ticket")
    markup.add(close_btn)
    return markup

def get_admin_ticket_markup(ticket_id, is_assigned=False):
    """Создает клавиатуру для админа при получении уведомления о новом обращении"""
    markup = InlineKeyboardMarkup()
    if not is_assigned:
        accept_btn = InlineKeyboardButton("✅ Принять обращение", callback_data=f"accept_ticket_{ticket_id}")
        markup.add(accept_btn)
    else:
        already_assigned_btn = InlineKeyboardButton("⚠️ Обращение уже принято другим админом", callback_data="already_assigned")
        markup.add(already_assigned_btn)
    
    view_btn = InlineKeyboardButton("👁️ Просмотреть обращение", callback_data=f"view_ticket_{ticket_id}")
    markup.add(view_btn)
    return markup

def get_admin_response_markup(ticket_id):
    """Создает клавиатуру для админа во время ответа на обращение"""
    markup = InlineKeyboardMarkup()
    finish_btn = InlineKeyboardButton("🏁 Завершить обработку", callback_data=f"finish_ticket_{ticket_id}")
    markup.add(finish_btn)
    return markup


# Клавиатуры для работы пользователя с его обращениями
def get_user_ticket_actions_markup(ticket_id: int):
    """Кнопки действий по выбранному обращению для пользователя"""
    markup = InlineKeyboardMarkup()
    continue_btn = InlineKeyboardButton("✍️ Продолжить переписку", callback_data=f"support_open_{ticket_id}")
    close_btn = InlineKeyboardButton("✅ Закрыть обращение", callback_data=f"support_close_{ticket_id}")
    back_btn = InlineKeyboardButton("⬅️ К списку обращений", callback_data="support_my_tickets")
    markup.add(continue_btn).add(close_btn).add(back_btn)
    return markup

def get_user_tickets_list_markup(tickets: list):
    """Создает список кнопок с обращениями пользователя"""
    markup = InlineKeyboardMarkup()
    for t in tickets:
        title = f"#{t.id} • {t.get_platform_display()} • {t.get_status_display()}"
        markup.add(InlineKeyboardButton(title, callback_data=f"support_ticket_{t.id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="help_main"))
    return markup


def get_admin_ticket_decision_markup(ticket_id: int):
    """Кнопки принятия или отказа от обращения после просмотра"""
    markup = InlineKeyboardMarkup()
    accept_btn = InlineKeyboardButton("✅ Принять обращение", callback_data=f"accept_ticket_{ticket_id}")
    decline_btn = InlineKeyboardButton("❌ Отказаться", callback_data=f"decline_ticket_{ticket_id}")
    markup.add(accept_btn).add(decline_btn)
    return markup


def get_admin_open_tickets_markup(tickets: list):
    """Список открытых необработанных обращений для админа"""
    markup = InlineKeyboardMarkup()
    for t in tickets:
        title = f"#{t.id} • {t.user.user_name} • {t.get_platform_display()}"
        markup.add(InlineKeyboardButton(title, callback_data=f"view_ticket_{t.id}"))
    markup.add(InlineKeyboardButton("⬅️ Админ-панель", callback_data="admin_panel"))
    return markup


def get_broadcast_confirm_markup():
    """Клавиатура подтверждения отправки рассылки"""
    markup = InlineKeyboardMarkup()
    confirm_btn = InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm")
    cancel_btn = InlineKeyboardButton("❌ Отменить", callback_data="broadcast_cancel")
    back_btn = InlineKeyboardButton("⬅️ Админ-панель", callback_data="admin_panel")
    markup.add(confirm_btn).add(cancel_btn).add(back_btn)
    return markup


def get_promocode_menu_markup():
    """Клавиатура меню промокодов"""
    markup = InlineKeyboardMarkup()
    add_btn = InlineKeyboardButton("➕ Добавить промокоды", callback_data="promocode_add")
    list_btn = InlineKeyboardButton("📋 Список промокодов", callback_data="promocode_list")
    back_btn = InlineKeyboardButton("⬅️ Админ-панель", callback_data="admin_panel")
    markup.add(add_btn).add(list_btn).add(back_btn)
    return markup


def get_promocode_list_markup(promocodes):
    """Клавиатура списка промокодов"""
    markup = InlineKeyboardMarkup()
    for promo in promocodes:
        status = "✅" if promo.is_active and not promo.is_used else "❌" if promo.is_used else "⏸️"
        btn_text = f"{promo.code} ({status})"
        btn = InlineKeyboardButton(btn_text, callback_data=f"promocode_detail_{promo.id}")
        markup.add(btn)
    
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="promocode_menu")
    markup.add(back_btn)
    return markup


def get_promocode_detail_markup(promo_id):
    """Клавиатура деталей промокода"""
    markup = InlineKeyboardMarkup()
    toggle_btn = InlineKeyboardButton("🔄 Изменить статус", callback_data=f"promocode_toggle_{promo_id}")
    delete_btn = InlineKeyboardButton("🗑️ Удалить", callback_data=f"promocode_delete_{promo_id}")
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="promocode_list")
    markup.add(toggle_btn).add(delete_btn).add(back_btn)
    return markup
