from telebot.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from bot import bot
from bot.texts import MAIN_TEXT, SUPPORT_TEXT, SUPPORT_LIMIT_REACHED, AI_ERROR
from bot.keyboards import main_markup, back_to_main_markup
from .registration import start_registration
from bot.models import goods, goods_category, User

def start(message: Message) -> None:
    # Отключаем режим ИИ при команде /start
    try:
        user = User.objects.get(telegram_id=message.chat.id)
        user.is_ai = False
        user.chat_history = {}
        user.save()
    except User.DoesNotExist:
        pass
    start_registration(message)

def menu_call(call: CallbackQuery) -> None:
    # Отключаем режим ИИ при нажатии кнопки назад
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        user.is_ai = False
        user.chat_history = {}
        user.save()
    except User.DoesNotExist:
        pass
    show_categories(call.message.chat.id, call.message.message_id)

def menu_m(message: Message) -> None:
    """Обработчик для отправки главного меню по текстовой команде"""
    user = User.objects.filter(telegram_id=message.chat.id).first()
    if user:
        # Отключаем режим ИИ
        user.is_ai = False
        user.chat_history = {}
        user.save()
    
    bot.send_message(
        chat_id=message.chat.id,
        text=MAIN_TEXT,
        reply_markup=main_markup
    )

def show_categories(chat_id: int, message_id: int = None) -> None:
    """Показать все категории товаров"""
    markup = InlineKeyboardMarkup()
    categories = goods_category.objects.all()
    
    for category in categories:
        btn = InlineKeyboardButton(
            category.name, 
            callback_data=f"category_{category.id}"
        )
        markup.add(btn)
    
    text = "Выберите категорию товаров:"
    
    if message_id:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup
        )

def show_category_products(call: CallbackQuery) -> None:
    """Показать товары в выбранной категории"""
    category_id = int(call.data.split('_')[1])
    category = goods_category.objects.get(id=category_id)
    products = goods.objects.filter(parent_category=category)
    
    markup = InlineKeyboardMarkup()
    for product in products:
        btn = InlineKeyboardButton(
            product.name,
            callback_data=f"product_{product.id}"
        )
        markup.add(btn)
    
    # Добавляем кнопку "Назад"
    back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
    markup.add(back_btn)
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Товары в категории {category.name}:",
        reply_markup=markup
    )

def show_product_menu(call: CallbackQuery) -> None:
    """Показать меню конкретного товара"""
    product_id = int(call.data.split('_')[1])
    product = goods.objects.get(id=product_id)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📖 Инструкция", callback_data=f"instructions_{product_id}"))
    markup.add(InlineKeyboardButton("❓ FAQ", callback_data=f"faq_{product_id}"))
    markup.add(InlineKeyboardButton("🛡️ Гарантия", callback_data=f"warranty_{product_id}"))
    markup.add(InlineKeyboardButton("📞 Поддержка", callback_data=f"support_{product_id}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"category_{product.parent_category.id}"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Информация о товаре: {product.name}",
        reply_markup=markup
    )

def send_long_message(chat_id: int, text: str, message_id: int = None) -> None:
    """Отправка длинного текста с разбивкой на сообщения"""
    # Максимальная длина одного сообщения
    MAX_LENGTH = 4096
    
    if len(text) <= MAX_LENGTH:
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text
            )
        else:
            bot.send_message(chat_id=chat_id, text=text)
    else:
        # Разбиваем текст на части
        parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
        for i, part in enumerate(parts):
            if i == 0 and message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=part
                )
            else:
                bot.send_message(chat_id=chat_id, text=part)

def show_product_info(call: CallbackQuery) -> None:
    """Показать информацию о товаре (инструкция/FAQ/гарантия)"""
    info_type, product_id = call.data.split('_')
    product_id = int(product_id)
    product = goods.objects.get(id=product_id)
    
    markup = InlineKeyboardMarkup()
    back_btn = InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{product_id}")
    markup.add(back_btn)
    
    if info_type == "instructions":
        text = f"📖 Инструкция по применению {product.name}:\n\n{product.instructions}"
    elif info_type == "faq":
        text = f"❓ Часто задаваемые вопросы о {product.name}:\n\n{product.FAQ}"
    elif info_type == "warranty":
        text = f"🛡️ Условия гарантии на {product.name}:\n\n{product.warranty}"
    elif info_type == "support":
        text = SUPPORT_TEXT
        user = User.objects.get(telegram_id=call.message.chat.id)
        user.is_ai = True
        user.chat_history = {}  # Сбрасываем историю чата
        user.save()
    else:
        return
    
    # Отправляем текст с учетом возможной длины
    send_long_message(call.message.chat.id, text, call.message.message_id)
    
    # Отправляем кнопку "Назад" отдельным сообщением, если текст был разбит
    if len(text) > 4096:
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Используйте кнопку ниже для навигации:",
            reply_markup=markup
        )
    else:
        # Если текст короткий, добавляем кнопку к сообщению
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

def chat_with_ai(message: Message) -> None:
    """Обработчик для общения с ИИ"""
    from bot.apis.ai import OpenAIAPI
    
    try:
        user = User.objects.get(telegram_id=message.chat.id)
        
        # Проверяем, активирован ли режим общения с ИИ
        if not user.is_ai:
            return
            
        # Проверяем количество уже отправленных сообщений
        chat_history = user.chat_history or {}
        if not isinstance(chat_history, dict):
            chat_history = {}
            
        ai_counter = chat_history.get('ai_counter', 0)
        
        # Если уже было отправлено 3 сообщения, отключаем ИИ и отправляем сообщение
        if ai_counter >= 3:
            user.is_ai = False
            user.chat_history = {}
            user.save()
            
            markup = InlineKeyboardMarkup()
            back_btn = InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")
            markup.add(back_btn)
            
            bot.send_message(
                chat_id=message.chat.id,
                text=SUPPORT_LIMIT_REACHED,
                reply_markup=markup
            )
            return
        
        # Отправляем сообщение о том, что бот печатает
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Получаем ответ от ИИ
        ai = OpenAIAPI()
        response = ai.get_response(message.chat.id, message.text)
        
        if response and 'message' in response:
            bot.send_message(message.chat.id, response['message'])
            
            # Увеличиваем счетчик сообщений
            chat_history['ai_counter'] = ai_counter + 1
            user.chat_history = chat_history
            user.save()
        else:
            bot.send_message(
                message.chat.id, 
                AI_ERROR
            )
    except User.DoesNotExist:
        # Если пользователь не существует, игнорируем сообщение
        pass
    except Exception as e:
        # В случае ошибки, отправляем сообщение об ошибке
        bot.send_message(
            message.chat.id, 
            AI_ERROR
        )
        print(f"Ошибка в chat_with_ai: {e}")

def back_to_main(call: CallbackQuery) -> None:
    """Обработчик для возврата в главное меню"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        user.is_ai = False
        user.chat_history = {}
        user.save()
    except User.DoesNotExist:
        pass
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=MAIN_TEXT,
        reply_markup=main_markup
    )

def support_menu(call: CallbackQuery) -> None:
    """Обработчик для отображения меню поддержки"""
    # Включаем режим ИИ для данного пользователя
    user = User.objects.get(telegram_id=call.message.chat.id)
    user.is_ai = True
    user.chat_history = {}  # Сбрасываем историю чата
    user.save()
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=SUPPORT_TEXT,
        reply_markup=back_to_main_markup
    )
