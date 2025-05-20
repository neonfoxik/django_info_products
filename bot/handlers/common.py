from telebot.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from bot import bot
from bot.texts import MAIN_TEXT, SUPPORT_TEXT, SUPPORT_LIMIT_REACHED, AI_ERROR
from bot.texts import EXTENDED_WARRANTY_TEXT, EXTENDED_WARRANTY_AVAILABLE, EXTENDED_WARRANTY_NOT_AVAILABLE
from bot.texts import EXTENDED_WARRANTY_ACTIVATION, SEND_SCREENSHOT, SCREENSHOT_VERIFICATION_FAILED
from bot.texts import EXTENDED_WARRANTY_ACTIVATED, SCREENSHOT_PROCESSING, SCREENSHOT_CHECKING, SCREENSHOT_INVALID, SCREENSHOT_VERIFIED
from bot.texts import EXTENDED_WARRANTY_ACTIVATED, SCREENSHOT_PROCESSING, SCREENSHOT_CHECKING, SCREENSHOT_INVALID, SCREENSHOT_VERIFIED, SCREENSHOT_LIMIT_REACHED
from bot.keyboards import main_markup, back_to_main_markup, get_product_menu_markup
from bot.keyboards import get_warranty_markup_with_extended, get_screenshot_markup
from .registration import start_registration
from bot.models import goods, goods_category, User
from bot.apis import analyze_screenshot
import json
import os
import logging
import time
import random
import traceback
from django.utils import timezone

# Словарь для отслеживания процесса активации расширенной гарантии
warranty_activation_state = {}

# Словарь для хранения состояния ручного подтверждения скриншотов
manual_confirmation_state = {}

logger = logging.getLogger(__name__)

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
    
    try:
        categories = goods_category.objects.all()
        
        # Проверяем, есть ли категории
        if not categories.exists():
            # Если категорий нет, показываем соответствующее сообщение
            text = "В настоящее время категории товаров не найдены. Пожалуйста, попробуйте позже."
            back_btn = InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu")
            markup.add(back_btn)
        else:
            # Если категории есть, показываем их
            for category in categories:
                btn = InlineKeyboardButton(
                    category.name, 
                    callback_data=f"category_{category.id}"
                )
                markup.add(btn)
        
        text = "Выберите категорию товаров:"
        
        # Отправляем сообщение
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
    
    except Exception as e:
        # В случае ошибки показываем сообщение об ошибке
        error_text = "Произошла ошибка при загрузке категорий. Пожалуйста, попробуйте позже."
        error_markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")
        error_markup.add(back_btn)
        
        print(f"[ERROR] Ошибка при показе категорий: {e}")
        logger.error(f"[ERROR] Ошибка при показе категорий: {e}")
        
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=error_text,
                reply_markup=error_markup
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text=error_text,
                reply_markup=error_markup
            )

def show_category_products(call: CallbackQuery) -> None:
    """Показать товары в выбранной категории"""
    try:
        category_id = int(call.data.split('_')[1])
        
        try:
            category = goods_category.objects.get(id=category_id)
        except goods_category.DoesNotExist:
            # Если категория не найдена, возвращаемся к списку категорий
            bot.answer_callback_query(call.id, "Категория не найдена. Возможно, она была удалена.")
            show_categories(call.message.chat.id, call.message.message_id)
            return
        
        products = goods.objects.filter(parent_category=category)
        
        markup = InlineKeyboardMarkup()
        
        # Проверяем, есть ли товары в категории
        if not products.exists():
            # Если товаров нет, показываем соответствующее сообщение
            text = f"В категории {category.name} пока нет товаров."
        else:
            # Если товары есть, показываем их
            for product in products:
                btn = InlineKeyboardButton(
                    product.name,
                    callback_data=f"product_{product.id}"
                )
                markup.add(btn)
            
            text = f"Товары в категории {category.name}:"
            
        # Добавляем кнопку "Назад"
        back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
        markup.add(back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup
        )
    
    except Exception as e:
        # В случае ошибки показываем сообщение об ошибке
        print(f"[ERROR] Ошибка при показе товаров категории: {e}")
        logger.error(f"[ERROR] Ошибка при показе товаров категории: {e}")
        
        error_markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
        error_markup.add(back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Произошла ошибка при загрузке товаров. Пожалуйста, попробуйте позже.",
            reply_markup=error_markup
        )

def show_product_menu(call: CallbackQuery) -> None:
    """Показать меню конкретного товара"""
    try:
        product_id = int(call.data.split('_')[1])
        
        try:
            product = goods.objects.get(id=product_id)
        except goods.DoesNotExist:
            # Если товар не найден, возвращаемся к списку категорий
            bot.answer_callback_query(call.id, "Товар не найден. Возможно, он был удален.")
            show_categories(call.message.chat.id, call.message.message_id)
            return
        
        markup = get_product_menu_markup(product_id)
    
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Информация о товаре: {product.name}",
            reply_markup=markup
        )
    
    except Exception as e:
        # В случае ошибки показываем сообщение об ошибке
        print(f"[ERROR] Ошибка при показе меню товара: {e}")
        logger.error(f"[ERROR] Ошибка при показе меню товара: {e}")
        
        error_markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
        error_markup.add(back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Произошла ошибка при загрузке информации о товаре. Пожалуйста, попробуйте позже.",
            reply_markup=error_markup
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
    try:
        info_type, product_id = call.data.split('_')
        product_id = int(product_id)
        
        try:
            product = goods.objects.get(id=product_id)
        except goods.DoesNotExist:
            # Если товар не найден, возвращаемся к списку категорий
            bot.answer_callback_query(call.id, "Товар не найден. Возможно, он был удален.")
            show_categories(call.message.chat.id, call.message.message_id)
            return
        
        markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{product_id}")
        markup.add(back_btn)
        
        if info_type == "instructions":
            text = f"📖 Инструкция по применению {product.name}:\n\n{product.instructions}"
        elif info_type == "faq":
            text = f"❓ Часто задаваемые вопросы о {product.name}:\n\n{product.FAQ}"
        elif info_type == "warranty":
            # Получаем информацию о расширенной гарантии
            try:
                user = User.objects.get(telegram_id=call.message.chat.id)
                extended_warranties = user.extended_warranty_products or {}
                
                if isinstance(extended_warranties, str):
                    extended_warranties = json.loads(extended_warranties)
                
                # Проверяем, есть ли расширенная гарантия на данный товар
                has_warranty = str(product_id) in extended_warranties
                
                # Форматируем срок гарантии для условий
                warranty_years = product.extended_warranty
                if warranty_years < 1:
                    months = int(warranty_years * 12)
                    warranty_period = f"{months} {'месяц' if months == 1 else 'месяца' if 1 < months < 5 else 'месяцев'}"
                else:
                    years = int(warranty_years) if warranty_years.is_integer() else warranty_years
                    if years == 1:
                        warranty_period = "1 год"
                    elif years in [2, 3, 4]:
                        warranty_period = f"{years} года"
                    else:
                        warranty_period = f"{years} лет"
                
                if has_warranty:
                    # Если у пользователя уже есть расширенная гарантия
                    extended_warranty_info = user.extended_warranty_info or {}
                    if isinstance(extended_warranty_info, str):
                        extended_warranty_info = json.loads(extended_warranty_info)
                    
                    warranty_info = extended_warranty_info.get(str(product_id), {})
                    
                    text = (
                        f"🛡️ Информация о расширенной гарантии на {product.name}:\n"
                        f"📅 Дата активации: {warranty_info.get('activation_date', 'Не указана')}\n"
                        f"⏳ Срок гарантии: {warranty_period}\n"
                        f"📆 Дата окончания: {warranty_info.get('end_date', 'Не указана')}"
                    )
                else:
                    # Если расширенной гарантии нет, показываем информацию о том, как её получить
                    text = (
                        f"🛡️ Условия гарантии на {product.name}:\n\n"
                        f"{product.warranty}\n\n"
                        f"✨ Как получить расширенную гарантию?\n\n"
                        f"1️⃣ Оставьте отзыв с 5 звездами о товаре\n"
                        f"2️⃣ Сделайте скриншот отзыва\n"
                        f"3️⃣ Отправьте скриншот боту\n\n"
                        f"После проверки отзыва, вы получите расширенную гарантию сроком на {warranty_period}!\n\n"
                        f"🛡️ Условия расширенной гарантии:\n"
                        f"{warranty_period}"
                    )
                
                # Создаем клавиатуру с кнопкой активации расширенной гарантии, если её нет
                markup = get_warranty_markup_with_extended(product_id, has_warranty)
                
            except Exception as e:
                # В случае ошибки, показываем только стандартную гарантию
                print(f"Ошибка при отображении информации о расширенной гарантии: {e}")
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
    
    except Exception as e:
        # В случае ошибки показываем сообщение об ошибке
        print(f"[ERROR] Ошибка при показе информации о товаре: {e}")
        logger.error(f"[ERROR] Ошибка при показе информации о товаре: {e}")
        
        error_markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
        error_markup.add(back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Произошла ошибка при загрузке информации. Пожалуйста, попробуйте позже.",
            reply_markup=error_markup
        )

def activate_warranty(call: CallbackQuery) -> None:
    """Запускает процесс активации расширенной гарантии"""
    try:
        product_id = int(call.data.split('_')[2])
        print(f"[LOG] Запрос на активацию гарантии от пользователя {call.message.chat.id} для товара {product_id}")
        logger.info(f"[LOG] Запрос на активацию гарантии от пользователя {call.message.chat.id} для товара {product_id}")
        
        product = goods.objects.get(id=product_id)
        
        # Сохраняем состояние активации гарантии
        warranty_activation_state[call.message.chat.id] = {
            'product_id': product_id,
            'waiting_for_screenshot': True
        }
        
        print(f"[LOG] Состояние ожидания скриншота установлено для пользователя {call.message.chat.id}")
        logger.info(f"[LOG] Состояние ожидания скриншота установлено для пользователя {call.message.chat.id}")
        
        markup = get_screenshot_markup(product_id)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=SEND_SCREENSHOT,
            reply_markup=markup
        )
        
        print(f"[LOG] Пользователю {call.message.chat.id} отправлен запрос на скриншот")
        logger.info(f"[LOG] Пользователю {call.message.chat.id} отправлен запрос на скриншот")
    except Exception as e:
        print(f"[ERROR] Ошибка при запуске активации гарантии: {e}")
        logger.error(f"[ERROR] Ошибка при запуске активации гарантии: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")

def cancel_warranty_activation(call: CallbackQuery) -> None:
    """Отменяет процесс активации расширенной гарантии"""
    try:
        product_id = int(call.data.split('_')[2])
        print(f"[LOG] Отмена активации гарантии пользователем {call.message.chat.id} для товара {product_id}")
        logger.info(f"[LOG] Отмена активации гарантии пользователем {call.message.chat.id} для товара {product_id}")
        
        # Удаляем состояние активации
        if call.message.chat.id in warranty_activation_state:
            del warranty_activation_state[call.message.chat.id]
            print(f"[LOG] Состояние ожидания скриншота удалено для пользователя {call.message.chat.id}")
            logger.info(f"[LOG] Состояние ожидания скриншота удалено для пользователя {call.message.chat.id}")
        
        # Возвращаемся к информации о товаре
        show_product_menu(call)
        
        print(f"[LOG] Пользователь {call.message.chat.id} возвращен в меню товара {product_id}")
        logger.info(f"[LOG] Пользователь {call.message.chat.id} возвращен в меню товара {product_id}")
    except Exception as e:
        print(f"[ERROR] Ошибка при отмене активации: {e}")
        logger.error(f"[ERROR] Ошибка при отмене активации: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")

def check_screenshot(message: Message) -> None:
    """Проверяет скриншот отзыва для активации расширенной гарантии"""
    try:
        print(f"[LOG] ПОЛУЧЕНА ФОТОГРАФИЯ ОТ ПОЛЬЗОВАТЕЛЯ {message.chat.id}")
        print(f"[LOG] Тип сообщения: {type(message)}")
        logger.info(f"[LOG] ПОЛУЧЕНА ФОТОГРАФИЯ ОТ ПОЛЬЗОВАТЕЛЯ {message.chat.id}")
        
        # Проверяем наличие фото
        if not message.photo:
            print(f"[LOG] СООБЩЕНИЕ НЕ СОДЕРЖИТ ФОТО")
            logger.info(f"[LOG] СООБЩЕНИЕ НЕ СОДЕРЖИТ ФОТО")
            return
        
        # Получаем или создаем пользователя
        user, created = User.objects.get_or_create(telegram_id=message.chat.id)
        
        # Проверяем лимит скриншотов в день
        today = timezone.now().date()
        
        # Если дата последнего скриншота не сегодня, сбрасываем счетчик
        if user.last_screenshot_date != today:
            user.screenshots_count = 0
            user.last_screenshot_date = today
        
        # Проверяем, не превышен ли лимит
        if user.screenshots_count >= 3:
            # Отправляем сообщение о лимите
            bot.send_message(
                chat_id=message.chat.id,
                text=SCREENSHOT_LIMIT_REACHED
            )
            print(f"[LOG] Пользователь {message.chat.id} достиг лимита скриншотов")
            logger.info(f"[LOG] Пользователь {message.chat.id} достиг лимита скриншотов")
            return
        
        # Увеличиваем счетчик скриншотов
        user.screenshots_count += 1
        user.save()
        print(f"[LOG] Счетчик скриншотов для пользователя {message.chat.id}: {user.screenshots_count}")
        logger.info(f"[LOG] Счетчик скриншотов для пользователя {message.chat.id}: {user.screenshots_count}")
        
        # Отправляем мгновенное подтверждение получения фото
        msg = bot.send_message(
            chat_id=message.chat.id,
            text=SCREENSHOT_PROCESSING
        )
        print(f"[LOG] Отправлено подтверждение получения фото")
        
        # Получаем фото максимального размера
        if message.photo:
            photo = message.photo[-1]
            file_id = photo.file_id
            print(f"[LOG] ID файла: {file_id}")
        
        # Если пользователь в процессе активации гарантии
        if message.chat.id in warranty_activation_state and warranty_activation_state[message.chat.id].get('waiting_for_screenshot'):
            print(f"[LOG] Пользователь в процессе активации гарантии")
            
            # Получаем информацию о товаре
            product_id = warranty_activation_state[message.chat.id]['product_id']
            print(f"[LOG] Product ID: {product_id}")
            
            # Обновляем сообщение с информацией о проверке
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                text=SCREENSHOT_CHECKING
            )
            print(f"[LOG] Сообщение обновлено: проверка скриншота")
            
            # Имитируем задержку обработки
            time.sleep(2)
            
            # Анализируем скриншот с помощью компьютерного зрения
            try:
                print(f"[LOG] Начинаем анализ скриншота")
                analysis_result = analyze_screenshot(photo, bot)
                print(f"[LOG] Результат анализа: {analysis_result}")
                
                is_valid = analysis_result['has_5_stars']
                confidence = analysis_result.get('confidence', 0)
                stars_count = analysis_result.get('stars_count', 0)
                
                # Логируем результат анализа
                print(f"[LOG] Скриншот содержит {stars_count} звезд, уверенность: {confidence}%")
                logger.info(f"[LOG] Скриншот содержит {stars_count} звезд, уверенность: {confidence}%")
                
                # Если скриншот не подтвержден или уверенность слишком низкая
                if not is_valid:
                    # Формируем сообщение в зависимости от количества звезд
                    if stars_count > 0 and stars_count < 5:
                        message_text = (
                            f"Мы сожалеем, что вам не понравился наш продукт. 😔\n\n"
                            f"В вашем отзыве обнаружено {stars_count} звезд. К сожалению, мы не можем предоставить вам расширенную гарантию, "
                            f"так как не выполнено условие получения - отзыв с 5 звездами.\n\n"
                            f"Для получения расширенной гарантии необходимо:\n"
                            f"1. Оставить отзыв с 5 звездами\n"
                            f"2. Отправить скриншот этого отзыва\n\n"
                            f"Вы можете изменить свой отзыв на 5 звезд и отправить новый скриншот."
                        )
                    else:
                        message_text = analysis_result.get('message', SCREENSHOT_INVALID)
                    
                    # Создаем клавиатуру с кнопками
                    markup = InlineKeyboardMarkup()
                    resend_btn = InlineKeyboardButton("🔄 Отправить другой скриншот", 
                                                     callback_data=f"cancel_review_{product_id}")
                    markup.add(resend_btn)
                    
                    # Сохраняем состояние ожидания ручного подтверждения
                    manual_confirmation_state[message.chat.id] = {
                        'product_id': product_id,
                        'message_id': msg.message_id,
                        'photo_id': photo.file_id
                    }
                    
                    # Отправляем сообщение с результатом проверки
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=msg.message_id,
                        text=message_text,
                        reply_markup=markup
                    )
                    
                    print(f"[LOG] Отправлено сообщение о необходимости 5 звезд")
                    logger.info(f"[LOG] Отправлено сообщение о необходимости 5 звезд")
                    return
                
                # Если скриншот прошел проверку
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    text=f"{SCREENSHOT_VERIFIED}\n\nУверенность определения: {confidence}%"
                )
                print(f"[LOG] Скриншот прошел проверку")
                logger.info(f"[LOG] Скриншот прошел проверку")
                
                # Активируем расширенную гарантию для пользователя
                activate_extended_warranty(message.chat.id, product_id, msg.message_id)
                
            except Exception as e:
                print(f"[ERROR] Ошибка при анализе скриншота: {e}")
                logger.error(f"[ERROR] Ошибка при анализе скриншота: {e}")
                
                # Сохраняем состояние ожидания ручного подтверждения
                manual_confirmation_state[message.chat.id] = {
                    'product_id': product_id,
                    'message_id': msg.message_id,
                    'photo_id': photo.file_id
                }
                
                print(f"[LOG] Запрос ручного подтверждения отправлен пользователю после ошибки")
                logger.info(f"[LOG] Запрос ручного подтверждения отправлен пользователю после ошибки")
                
        else:
            # Если пользователь не в процессе активации гарантии
            print(f"[LOG] Пользователь не в процессе активации гарантии")
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                text="Спасибо за фотографию! Если вы хотите активировать расширенную гарантию, перейдите в раздел гарантии товара."
            )
    
    except Exception as e:
        print(f"[ERROR] ОШИБКА В ФУНКЦИИ check_screenshot: {e}")
        logger.error(f"[ERROR] ОШИБКА В ФУНКЦИИ check_screenshot: {e}")
        print(f"[ERROR] Тип ошибки: {type(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # Отправляем уведомление об ошибке пользователю
        bot.send_message(
            chat_id=message.chat.id,
            text=f"Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте еще раз."
        )

def activate_extended_warranty(chat_id, product_id, message_id=None):
    """Активирует расширенную гарантию для пользователя"""
    try:
        print(f"[LOG] Активация расширенной гарантии для пользователя {chat_id} на товар {product_id}")
        
        product = goods.objects.get(id=product_id)
        user = User.objects.get(telegram_id=chat_id)
        
        extended_warranties = user.extended_warranty_products or {}
        if isinstance(extended_warranties, str):
            extended_warranties = json.loads(extended_warranties)
            
        extended_warranty_info = user.extended_warranty_info or {}
        if isinstance(extended_warranty_info, str):
            extended_warranty_info = json.loads(extended_warranty_info)
        
        # Добавляем товар в список товаров с расширенной гарантией
        extended_warranties[str(product_id)] = True
        
        # Рассчитываем дату окончания гарантии
        current_date = timezone.now()
        warranty_years = product.extended_warranty
        end_date = current_date + timezone.timedelta(days=int(warranty_years * 365))
        
        # Форматируем дату окончания
        end_date_str = end_date.strftime("%d.%m.%Y")
        
        # Форматируем срок гарантии
        if warranty_years.is_integer():
            warranty_text = f"{int(warranty_years)} {'год' if warranty_years == 1 else 'года' if 1 < warranty_years < 5 else 'лет'}"
        else:
            months = int(warranty_years * 12)
            warranty_text = f"{months} {'месяц' if months == 1 else 'месяца' if 1 < months < 5 else 'месяцев'}"
        
        # Сохраняем информацию о товаре
        extended_warranty_info[str(product_id)] = {
            'name': product.name,
            'activation_date': current_date.strftime("%d.%m.%Y"),
            'end_date': end_date_str,
            'warranty_period': warranty_text
        }
        
        user.extended_warranty_products = extended_warranties
        user.extended_warranty_info = extended_warranty_info
        user.save()
        
        print(f"[LOG] Гарантия активирована для товара {product_id}")
        
        # Формируем сообщение об успешной активации
        success_text = (
            f"✅ Расширенная гарантия успешно активирована!\n\n"
            f"🛡️ Информация о расширенной гарантии на {product.name}:\n"
            f"📅 Дата активации: {current_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Срок гарантии: {warranty_text}\n"
            f"📆 Дата окончания: {end_date_str}"
        )
        
        # Отправляем сообщение об успешной активации
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=success_text
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text=success_text
            )
        
        # Добавляем кнопку возврата
        markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Вернуться к товару", callback_data=f"product_{product_id}")
        markup.add(back_btn)
        
        bot.send_message(
            chat_id=chat_id,
            text="Используйте кнопку ниже, чтобы вернуться к информации о товаре:",
            reply_markup=markup
        )
        
        # Удаляем состояние активации гарантии
        if chat_id in warranty_activation_state:
            del warranty_activation_state[chat_id]
        
        # Удаляем состояние ручного подтверждения, если оно было
        if chat_id in manual_confirmation_state:
            del manual_confirmation_state[chat_id]
            
    except Exception as e:
        print(f"[ERROR] Ошибка при активации гарантии: {e}")
        logger.error(f"[ERROR] Ошибка при активации гарантии: {e}")
        
        # Отправляем сообщение об ошибке
        bot.send_message(
            chat_id=chat_id,
            text=f"Произошла ошибка при активации гарантии: {e}"
        )

def confirm_review(call: CallbackQuery) -> None:
    """Обработчик для ручного подтверждения скриншота с отзывом"""
    try:
        product_id = int(call.data.split('_')[2])
        chat_id = call.message.chat.id
        
        print(f"[LOG] Пользователь {chat_id} подтвердил скриншот отзыва для товара {product_id}")
        logger.info(f"[LOG] Пользователь {chat_id} подтвердил скриншот отзыва для товара {product_id}")
        
        # Активируем расширенную гарантию
        activate_extended_warranty(chat_id, product_id, call.message.message_id)
        
    except Exception as e:
        print(f"[ERROR] Ошибка при ручном подтверждении скриншота: {e}")
        logger.error(f"[ERROR] Ошибка при ручном подтверждении скриншота: {e}")
        
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

def cancel_review(call: CallbackQuery) -> None:
    """Обработчик для отмены ручного подтверждения скриншота"""
    try:
        product_id = int(call.data.split('_')[2])
        chat_id = call.message.chat.id
        
        print(f"[LOG] Пользователь {chat_id} отменил подтверждение скриншота для товара {product_id}")
        logger.info(f"[LOG] Пользователь {chat_id} отменил подтверждение скриншота для товара {product_id}")
        
        # Если было состояние ручного подтверждения, удаляем его
        if chat_id in manual_confirmation_state:
            del manual_confirmation_state[chat_id]
        
        # Отправляем сообщение с просьбой отправить новый скриншот
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=SEND_SCREENSHOT
        )
        
    except Exception as e:
        print(f"[ERROR] Ошибка при отмене подтверждения скриншота: {e}")
        logger.error(f"[ERROR] Ошибка при отмене подтверждения скриншота: {e}")
        
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

def show_my_warranties(call: CallbackQuery) -> None:
    """Показывает список товаров с активированной расширенной гарантией"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        extended_warranties = user.extended_warranty_products or {}
        extended_warranty_info = user.extended_warranty_info or {}
        
        if isinstance(extended_warranties, str):
            extended_warranties = json.loads(extended_warranties)
        if isinstance(extended_warranty_info, str):
            extended_warranty_info = json.loads(extended_warranty_info)
        
        if not extended_warranties:
            # Если нет активированных гарантий
            text = "У вас пока нет активированных расширенных гарантий на товары."
        else:
            # Формируем список товаров с расширенной гарантией
            text = "🛡️ Товары с активированной расширенной гарантией:\n\n"
            current_date = timezone.now().date()
            
            for product_id in extended_warranties:
                try:
                    product_info = extended_warranty_info.get(str(product_id))
                    if product_info:
                        # Проверяем, не истек ли срок гарантии
                        end_date = timezone.datetime.strptime(product_info['end_date'], "%d.%m.%Y").date()
                        if current_date > end_date:
                            status = "❌ Истекла"
                        else:
                            status = "✅ Активна"
                            
                        text += (
                            f"{status}\n"
                            f"📱 {product_info['name']}\n"
                            f"⏳ Срок: {product_info['warranty_period']}\n"
                            f"📅 Активация: {product_info['activation_date']}\n"
                            f"📆 Окончание: {product_info['end_date']}\n\n"
                        )
                    else:
                        # Если информация о товаре не найдена, пытаемся получить её из базы данных
                        product = goods.objects.get(id=int(product_id))
                        current_date = timezone.now()
                        warranty_years = product.extended_warranty
                        end_date = current_date + timezone.timedelta(days=int(warranty_years * 365))
                        
                        # Форматируем срок гарантии
                        if warranty_years.is_integer():
                            warranty_text = f"{int(warranty_years)} {'год' if warranty_years == 1 else 'года' if 1 < warranty_years < 5 else 'лет'}"
                        else:
                            months = int(warranty_years * 12)
                            warranty_text = f"{months} {'месяц' if months == 1 else 'месяца' if 1 < months < 5 else 'месяцев'}"
                        
                        product_info = {
                            'name': product.name,
                            'activation_date': current_date.strftime("%d.%m.%Y"),
                            'end_date': end_date.strftime("%d.%m.%Y"),
                            'warranty_period': warranty_text
                        }
                        
                        text += (
                            f"✅ Активна\n"
                            f"📱 {product_info['name']}\n"
                            f"⏳ Срок: {product_info['warranty_period']}\n"
                            f"📅 Активация: {product_info['activation_date']}\n"
                            f"📆 Окончание: {product_info['end_date']}\n\n"
                        )
                        
                        # Сохраняем информацию для будущего использования
                        extended_warranty_info[str(product_id)] = product_info
                except goods.DoesNotExist:
                    continue
            
            # Сохраняем обновленную информацию
            user.extended_warranty_info = extended_warranty_info
            user.save()
        
        markup = back_to_main_markup
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=markup
            )
        except Exception as e:
            # Если не удалось отредактировать сообщение, отправляем новое
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                reply_markup=markup
            )
            
    except User.DoesNotExist:
        # Если пользователь не найден, отправляем сообщение об ошибке
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Произошла ошибка при получении информации о гарантиях. Пожалуйста, попробуйте позже.",
            reply_markup=back_to_main_markup
        )
    except Exception as e:
        print(f"Ошибка при отображении списка расширенных гарантий: {e}")
        logger.error(f"Ошибка при отображении списка расширенных гарантий: {e}")
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.",
            reply_markup=back_to_main_markup
        )

def chat_with_ai(message: Message) -> None:
    """Обработчик для общения с ИИ"""
    try:
        # Проверяем, не является ли сообщение скриншотом для активации гарантии
        if message.photo:
            print(f"[LOG] Получена фотография от пользователя {message.chat.id}")
            logger.info(f"[LOG] Получена фотография от пользователя {message.chat.id}")
            
            # Принудительно вызываем обработку скриншота, если пришло фото
            check_screenshot(message)
            return
        
        from bot.apis.ai import OpenAIAPI
    
        user = User.objects.get(telegram_id=message.chat.id)
        
        # Проверяем, активирован ли режим общения с ИИ
        if not user.is_ai:
            print(f"[LOG] Пользователь {message.chat.id} не в режиме AI")
            logger.info(f"[LOG] Пользователь {message.chat.id} не в режиме AI")
            return
            
        # Проверяем количество уже отправленных сообщений
        chat_history = user.chat_history or {}
        if not isinstance(chat_history, dict):
            chat_history = {}
            
        ai_counter = chat_history.get('ai_counter', 0)
        
        print(f"[LOG] Запрос к AI от пользователя {message.chat.id}, счетчик: {ai_counter}")
        logger.info(f"[LOG] Запрос к AI от пользователя {message.chat.id}, счетчик: {ai_counter}")
        
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
            
            print(f"[LOG] Лимит сообщений к AI превышен для пользователя {message.chat.id}")
            logger.info(f"[LOG] Лимит сообщений к AI превышен для пользователя {message.chat.id}")
            return
        
        # Отправляем сообщение о том, что бот печатает
        bot.send_chat_action(message.chat.id, 'typing')
        
        print(f"[LOG] Отправка запроса к AI API: {message.text}")
        logger.info(f"[LOG] Отправка запроса к AI API: {message.text}")
        
        # Получаем ответ от ИИ
        ai = OpenAIAPI()
        response = ai.get_response(message.chat.id, message.text)
        
        if response and 'message' in response:
            bot.send_message(message.chat.id, response['message'])
            
            # Увеличиваем счетчик сообщений
            chat_history['ai_counter'] = ai_counter + 1
            user.chat_history = chat_history
            user.save()
            
            print(f"[LOG] Получен ответ от AI, новый счетчик: {ai_counter + 1}")
            logger.info(f"[LOG] Получен ответ от AI, новый счетчик: {ai_counter + 1}")
        else:
            bot.send_message(
                message.chat.id, 
                AI_ERROR
            )
            print(f"[ERROR] Ошибка получения ответа от AI API")
            logger.error(f"[ERROR] Ошибка получения ответа от AI API")
    except User.DoesNotExist:
        # Если пользователь не существует, игнорируем сообщение
        print(f"[LOG] Пользователь {message.chat.id} не найден в базе данных")
        logger.info(f"[LOG] Пользователь {message.chat.id} не найден в базе данных")
        pass
    except Exception as e:
        # В случае ошибки, отправляем сообщение об ошибке
        bot.send_message(
            message.chat.id, 
            AI_ERROR
        )
        print(f"[ERROR] Ошибка в chat_with_ai: {e}")
        logger.error(f"[ERROR] Ошибка в chat_with_ai: {e}")

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

def back_to_categories(call: CallbackQuery) -> None:
    """Обработчик для возврата к списку категорий"""
    show_categories(call.message.chat.id, call.message.message_id)

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
