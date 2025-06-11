from telebot.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from bot import bot
from bot.texts import MAIN_TEXT, SUPPORT_TEXT, SUPPORT_LIMIT_REACHED, AI_ERROR
from bot.texts import SEND_SCREENSHOT, SCREENSHOT_PROCESSING, SCREENSHOT_CHECKING, SCREENSHOT_INVALID, SCREENSHOT_VERIFIED, SCREENSHOT_LIMIT_REACHED
from bot.texts import WARRANTY_CONDITIONS_TEXT
from bot.keyboards import main_markup, back_to_main_markup, get_product_menu_markup
from bot.keyboards import get_warranty_markup_with_extended, get_screenshot_markup, get_warranty_main_menu_markup
from .registration import start_registration
from bot.models import goods, goods_category, User, AdminContact, FAQ, ProductDocument
from bot.apis import analyze_screenshot
from bot.apis.ai import OpenAIAPI
from functools import wraps
import json
import os
import logging
import time
import random
import traceback
from django.utils import timezone
from django.conf import settings
from bot.utils.excel_handler import WarrantyExcelHandler
from telebot import TeleBot
import re

# Словарь для отслеживания процесса активации расширенной гарантии
warranty_activation_state = {}

# Словарь для хранения состояния ручного подтверждения скриншотов
manual_confirmation_state = {}

# Словарь для отслеживания состояния запроса номера телефона для гарантийных случаев
warranty_case_phone_state = {}

# Словарь для отслеживания состояния запроса описания проблемы
warranty_case_description_state = {}

logger = logging.getLogger(__name__)


def disable_ai_mode(func):
    """Декоратор для отключения режима ИИ при вызове функции"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Получаем объект call из аргументов
        call = next((arg for arg in args if isinstance(arg, CallbackQuery)), None)
        if call and not call.data.startswith('support_'):
            try:
                user = User.objects.get(telegram_id=call.message.chat.id)
                user.is_ai = False
                user.chat_history = {}
                user.save()
            except User.DoesNotExist:
                pass
        return func(*args, **kwargs)
    return wrapper

@disable_ai_mode
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

@disable_ai_mode
def menu_call(call: CallbackQuery) -> None:
    """Обработчик для возврата в главное меню"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        user.is_ai = False
        user.chat_history = {}
        user.save()
    except User.DoesNotExist:
        pass

    # Редактируем текущее сообщение на главное меню
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=MAIN_TEXT,
        reply_markup=main_markup
    )

@disable_ai_mode
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

@disable_ai_mode
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
            
            # Добавляем кнопку возврата в главное меню
            back_btn = InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")
            markup.add(back_btn)
        
        text = "Выберите категорию товаров:"
        
        # Редактируем существующее сообщение
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

@disable_ai_mode
def show_category_products(call: CallbackQuery) -> None:
    """Показывает список товаров в категории"""
    try:
        parts = call.data.split('_')
        if len(parts) != 2:
            raise ValueError("Неверный формат callback_data")
        category_id = int(parts[1])
        
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


@disable_ai_mode
def delete_previous_messages(chat_id: int, user: User) -> None:
    """Удаляет предыдущие сообщения пользователя"""
    if user.messages_count > 0:
        for i in range(user.messages_count - 1):
            try:
                bot.delete_message(chat_id=chat_id, message_id=int(user.last_message_id) - i - 1)
            except Exception as e:
                print(f"[ERROR] Ошибка при удалении сообщения: {e}")
        user.messages_count = 0
        user.last_message_id = None
        user.save()


@disable_ai_mode
def show_product_menu(call: CallbackQuery) -> None:
    """Показывает меню товара"""
    try:
        parts = call.data.split('_')
        if len(parts) != 2:
            raise ValueError("Неверный формат callback_data")
        product_id = int(parts[1])
        
        try:
            user = User.objects.get(telegram_id=call.message.chat.id)
            # Удаляем предыдущие сообщения
            delete_previous_messages(call.message.chat.id, user)
        except User.DoesNotExist:
            pass
        
        try:
            product = goods.objects.get(id=product_id)
        except goods.DoesNotExist:
            # Если товар не найден, возвращаемся к списку категорий
            bot.answer_callback_query(call.id, "Товар не найден. Возможно, он был удален.")
            show_categories(call.message.chat.id, call.message.message_id)
            return
        
        markup = get_product_menu_markup(product_id)
        
        # Проверяем, является ли текущее сообщение сообщением с PDF
        if call.message.content_type != 'text':
            try:
                # Удаляем старое сообщение
                bot.delete_message(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
            except Exception as e:
                print(f"[ERROR] Ошибка при удалении сообщения: {e}")
                logger.error(f"[ERROR] Ошибка при удалении сообщения: {e}")
            
            # Отправляем новое сообщение с меню
            bot.send_message(
                chat_id=call.message.chat.id,
                text=f"Информация о товаре: {product.name}",
                reply_markup=markup
            )
        else:
            # Если это обычное текстовое сообщение, редактируем его
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
        
        # Проверяем тип сообщения
        if call.message.content_type != 'text':
            try:
                # Удаляем старое сообщение
                bot.delete_message(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
            except Exception as e:
                print(f"[ERROR] Ошибка при удалении сообщения: {e}")
                logger.error(f"[ERROR] Ошибка при удалении сообщения: {e}")
            
            # Отправляем новое сообщение с ошибкой
            bot.send_message(
                chat_id=call.message.chat.id,
                text="Произошла ошибка при загрузке информации о товаре. Пожалуйста, попробуйте позже.",
                reply_markup=error_markup
            )
        else:
            # Если это обычное текстовое сообщение, редактируем его
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Произошла ошибка при загрузке информации о товаре. Пожалуйста, попробуйте позже.",
                reply_markup=error_markup
            )

@disable_ai_mode
def send_long_message(chat_id: int, text: str, message_id: int = None, markup=None) -> None:
    """Отправка длинного текста с разбивкой на сообщения"""
    # Максимальная длина одного сообщения
    MAX_LENGTH = 4096
    
    try:
        user = User.objects.get(telegram_id=chat_id)
        
        if len(text) <= MAX_LENGTH:
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=markup
                )
                user.last_message_id = str(message_id)
            else:
                msg = bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=markup
                )
                user.last_message_id = str(msg.message_id)
            user.messages_count = 1
        else:
            # Разбиваем текст на части
            parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
            for i, part in enumerate(parts):
                if i == 0 and message_id:
                    msg = bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=part
                    )
                    user.last_message_id = str(message_id)
                else:
                    msg = bot.send_message(
                        chat_id=chat_id,
                        text=part,
                        reply_markup=markup if i == len(parts) - 1 else None
                    )
                    if i == len(parts) - 1:
                        user.last_message_id = str(msg.message_id)
            user.messages_count = len(parts)
        
        user.save()
        
    except User.DoesNotExist:
        # Если пользователь не найден, просто отправляем сообщение
        if len(text) <= MAX_LENGTH:
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
        else:
            parts = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
            for i, part in enumerate(parts):
                if i == 0 and message_id:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=part
                    )
                else:
                    bot.send_message(
                        chat_id=chat_id,
                        text=part,
                        reply_markup=markup if i == len(parts) - 1 else None
                    )


@disable_ai_mode
def reset_user_messages(user: User) -> None:
    """Сбрасывает счетчик сообщений пользователя"""
    user.messages_count = 0
    user.last_message_id = None
    user.save()

@disable_ai_mode
def show_product_info(call: CallbackQuery) -> None:
    """Показывает информацию о товаре (инструкция/FAQ/гарантия)"""
    try:
        # Специальная обработка для FAQ PDF
        if call.data.startswith('faq_pdf_'):
            send_faq_pdf(call, bot)
            return
        
        # Специальная обработка для Instruction PDF (старый формат FAQ)
        if call.data.startswith('instruction_pdf_'):
            send_instruction_pdf(call, bot)
            return
            
        # Специальная обработка для Product Instruction PDF (новый формат)
        if call.data.startswith('product_instruction_pdf_'):
            send_product_instruction_pdf(call)
            return
        
        # Получаем тип информации и ID товара из callback_data
        parts = call.data.split('_')
        if len(parts) < 2:
            raise ValueError("Неверный формат callback_data")
            
        info_type = parts[0]
        product_id = int(parts[1])
        
        # Проверяем, что тип информации валидный
        if info_type not in ['instructions', 'faq', 'warranty']:
            raise ValueError(f"Неизвестный тип информации: {info_type}")
        
        product = goods.objects.get(id=product_id)
        user = User.objects.get(telegram_id=call.message.chat.id)
        warranty_data = user.warranty_data or {}
        product_data = warranty_data.get(str(product_id), {})
        has_warranty = product_data.get('is_active', False)

        # Только для раздела "Гарантия" показываем кнопку активации
        if info_type == "warranty":
            markup = get_warranty_markup_with_extended(product_id, has_warranty)
        else:
            # Для других разделов — только кнопка назад к товару
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{product_id}"))

        # Удаляем предыдущее сообщение
        try:
            bot.delete_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении сообщения: {e}")
            logger.error(f"[ERROR] Ошибка при удалении сообщения: {e}")
        
        if info_type == "instructions":
            # Получаем документ с инструкцией
            doc = product.documents.filter(document_type='instructions').first()
            if doc and doc.pdf_file:
                # Отправляем PDF файл напрямую
                with open(doc.pdf_file.path, 'rb') as pdf:
                    bot.send_document(
                        chat_id=call.message.chat.id,
                        document=pdf,
                        caption=f"📖 Инструкция по применению {product.name}",
                        reply_markup=markup
                    )
            else:
                text = f"📖 Инструкция для товара {product.name} отсутствует."
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=markup
                )
        elif info_type == "faq":
            # Получаем все активные FAQ для товара
            faqs = FAQ.objects.filter(
                product=product, 
                is_active=True
            ).order_by('order', 'title')
            
            if faqs.exists():
                # Создаем клавиатуру с FAQ
                markup = InlineKeyboardMarkup()
                
                for faq in faqs:
                    btn = InlineKeyboardButton(
                        faq.title,
                        callback_data=f"faq_pdf_{faq.id}"
                    )
                    markup.add(btn)
                
                # Добавляем кнопку назад
                back_btn = InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu")
                markup.add(back_btn)
                
                text = f"❓ Часто задаваемые вопросы о {product.name}:\n\nВыберите интересующий вопрос:"
                bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=markup
                )
            else:
                # Если FAQ нет, проверяем старый формат (ProductDocument)
                doc = product.documents.filter(document_type='faq').first()
                if doc:
                    if doc.pdf_file and doc.text_content:
                        # Если есть и PDF файл, и текст, отправляем их одним сообщением
                        text = f"❓ Часто задаваемые вопросы о {product.name}:\n\n{doc.text_content}"
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=text,
                                reply_markup=markup
                            )
                    elif doc.pdf_file:
                        # Если есть только PDF файл
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=f"❓ Часто задаваемые вопросы о {product.name}",
                                reply_markup=markup
                            )
                    elif doc.text_content:
                        # Если есть только текст
                        text = f"❓ Часто задаваемые вопросы о {product.name}:\n\n{doc.text_content}"
                        bot.send_message(
                            chat_id=call.message.chat.id,
                            text=text,
                            reply_markup=markup
                        )
                else:
                    text = f"❓ Часто задаваемые вопросы о {product.name} отсутствуют."
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu"))
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        reply_markup=markup
                    )
        elif info_type == "warranty":
            # Получаем документ с гарантией
            doc = product.documents.filter(document_type='warranty').first()
            
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
                product_info = product_data.get('info', {})
                
                text = (
                    f"🛡️ Информация о расширенной гарантии на {product.name}:\n"
                    f"📅 Дата активации: {product_info.get('activation_date', 'Не указана')}\n"
                    f"⏳ Срок гарантии: {product_info.get('warranty_period', warranty_period)}\n"
                    f"📆 Дата окончания: {product_info.get('end_date', 'Не указана')}"
                )
                
                if doc:
                    if doc.pdf_file and doc.text_content:
                        # Если есть и PDF файл, и текст, отправляем их одним сообщением
                        full_text = f"{text}\n\n{doc.text_content}"
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=full_text,
                                reply_markup=markup
                            )
                    elif doc.pdf_file:
                        # Если есть только PDF файл
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=text,
                                reply_markup=markup
                            )
                    elif doc.text_content:
                        # Если есть только текст
                        bot.send_message(
                            chat_id=call.message.chat.id,
                            text=f"{text}\n\n{doc.text_content}",
                            reply_markup=markup
                        )
                else:
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        reply_markup=markup
                    )
            else:
                # Если расширенной гарантии нет, показываем информацию о том, как её получить
                if doc:
                    if doc.pdf_file and doc.text_content:
                        # Если есть и PDF файл, и текст, отправляем их одним сообщением
                        text = (
                            f"✨ Как получить расширенную гарантию?\n\n"
                            f"1️⃣ Оставьте отзыв с 5 звездами о товаре\n"
                            f"2️⃣ Сделайте скриншот отзыва\n"
                            f"3️⃣ Отправьте скриншот боту\n\n"
                            f"После проверки отзыва, вы получите расширенную гарантию сроком на {warranty_period}!\n\n"
                            f"🛡️ Условия расширенной гарантии:\n"
                            f"{warranty_period}"
                        )
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=text,
                                reply_markup=markup
                            )
                    elif doc.pdf_file:
                        # Если есть только PDF файл
                        with open(doc.pdf_file.path, 'rb') as pdf:
                            bot.send_document(
                                chat_id=call.message.chat.id,
                                document=pdf,
                                caption=f"🛡️ Условия гарантии на {product.name}",
                                reply_markup=markup
                            )
                    elif doc.text_content:
                        # Если есть только текст
                        text = (
                            f"🛡️ Условия гарантии на {product.name}:\n\n"
                            f"{doc.text_content}\n\n"
                            f"✨ Как получить расширенную гарантию?\n\n"
                            f"1️⃣ Оставьте отзыв с 5 звездами о товаре\n"
                            f"2️⃣ Сделайте скриншот отзыва\n"
                            f"3️⃣ Отправьте скриншот боту\n\n"
                            f"После проверки отзыва, вы получите расширенную гарантию сроком на {warranty_period}!\n\n"
                            f"🛡️ Условия расширенной гарантии:\n"
                            f"{warranty_period}"
                        )
                        bot.send_message(
                            chat_id=call.message.chat.id,
                            text=text,
                            reply_markup=markup
                        )
                else:
                    text = (
                        f"✨ Как получить расширенную гарантию?\n\n"
                        f"1️⃣ Оставьте отзыв с 5 звездами о товаре\n"
                        f"2️⃣ Сделайте скриншот отзыва\n"
                        f"3️⃣ Отправьте скриншот боту\n\n"
                        f"После проверки отзыва, вы получите расширенную гарантию сроком на {warranty_period}!"
                    )
                    bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        reply_markup=markup
                    )
                
        elif info_type == "support":
            text = SUPPORT_TEXT
            user = User.objects.get(telegram_id=call.message.chat.id)
            user.is_ai = True
            user.chat_history = {}  # Сбрасываем историю чата
            user.save()
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                reply_markup=markup
            )
        else:
            return
    
    except Exception as e:
        print(f"[ERROR] Ошибка при показе информации о товаре: {e}")
        logger.error(f"[ERROR] Ошибка при показе информации о товаре: {e}")
        
        error_markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")
        error_markup.add(back_btn)
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Произошла ошибка при загрузке информации. Пожалуйста, попробуйте позже.",
            reply_markup=error_markup
        )


@disable_ai_mode
def activate_warranty(call: CallbackQuery) -> None:
    """Начинает процесс активации расширенной гарантии"""
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
        product_id = int(parts[2])
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

@disable_ai_mode
def cancel_warranty_activation(call: CallbackQuery) -> None:
    """Отменяет процесс активации расширенной гарантии"""
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
        product_id = int(parts[2])
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

@disable_ai_mode
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
                analysis_result = analyze_screenshot(photo, bot, product_id)
                print(f"[LOG] Результат анализа: {analysis_result}")
                
                is_valid = analysis_result['has_5_stars']
                confidence = analysis_result.get('confidence', 0)
                stars_count = analysis_result.get('stars_count', 0)
                review_date = analysis_result.get('review_date')
                product_match = analysis_result.get('product_match')
                
                # Логируем результат анализа
                print(f"[LOG] Скриншот содержит {stars_count} звезд, уверенность: {confidence}%")
                if review_date:
                    print(f"[LOG] Дата отзыва: {review_date}")
                if product_match is not None:
                    print(f"[LOG] Соответствие товара: {product_match}")
                logger.info(f"[LOG] Скриншот содержит {stars_count} звезд, уверенность: {confidence}%")
                
                # Отправляем информацию в лог-чат
                if settings.CHAT_LOG_ID:
                    try:
                        product = goods.objects.get(id=product_id)
                        # Если дата отзыва не определена, используем текущую дату
                        review_date = review_date if review_date else timezone.now().strftime("%d.%m.%Y")
                        log_message = (
                            f"📸 Новый скриншот отзыва\n\n"
                            f"👤 Пользователь: {user.user_name} (ID: {user.telegram_id})\n"
                            f"📱 Товар: {product.name}\n"
                            f"⭐️ Количество звезд: {stars_count}\n"
                            f"📊 Уверенность: {confidence}%\n"
                            f"📅 Дата отзыва: {review_date}\n"
                        )
                        if product_match is not None:
                            log_message += f"🔄 Соответствие товара: {'Да' if product_match else 'Нет'}\n"
                        log_message += f"✅ Результат проверки: {'Успешно' if is_valid else 'Не пройдена'}"
                        
                        # Отправляем скриншот с информацией одним сообщением
                        bot.send_photo(
                            chat_id=settings.CHAT_LOG_ID,
                            photo=file_id,
                            caption=log_message
                        )
                    except Exception as e:
                        print(f"[ERROR] Ошибка при отправке лога: {e}")
                        logger.error(f"[ERROR] Ошибка при отправке лога: {e}")
                
                # Если скриншот не подтвержден или уверенность слишком низкая
                if not is_valid or (product_match is False):
                    # Формируем сообщение в зависимости от результатов проверки
                    message_parts = []
                    
                    if stars_count > 0 and stars_count < 5:
                        message_parts.append(
                            f"Мы сожалеем, что вам не понравился наш продукт. 😔\n\n"
                            f"В вашем отзыве обнаружено {stars_count} звезд. К сожалению, мы не можем предоставить вам расширенную гарантию, "
                            f"так как не выполнено условие получения - отзыв с 5 звездами.\n\n"
                            f"Для получения расширенной гарантии необходимо:\n"
                            f"1. Оставить отзыв с 5 звездами\n"
                            f"2. Отправить скриншот этого отзыва\n\n"
                            f"Вы можете изменить свой отзыв на 5 звезд и отправить новый скриншот."
                        )
                    elif product_match is False:
                        message_parts.append(
                            "Товар в отзыве не соответствует запрошенному. Пожалуйста, убедитесь, что вы отправляете скриншот отзыва правильного товара."
                        )
                    else:
                        message_parts.append(analysis_result.get('message', SCREENSHOT_INVALID))
                    
                    message_text = "\n\n".join(message_parts)
                    
                    # Создаем клавиатуру с кнопками
                    markup = InlineKeyboardMarkup()
                    resend_btn = InlineKeyboardButton("🔄 Отправить другой скриншот", 
                                                     callback_data=f"cancel_review_{product_id}")
                    markup.add(resend_btn)
                    
                    # Сохраняем состояние ожидания ручного подтверждения
                    manual_confirmation_state[message.chat.id] = {
                        'product_id': product_id,
                        'message_id': msg.message_id,
                        'photo_id': photo.file_id,
                        'review_date': review_date
                    }
                    
                    # Отправляем сообщение с результатом проверки
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=msg.message_id,
                        text=message_text,
                        reply_markup=markup
                    )
                    
                    print(f"[LOG] Отправлено сообщение о необходимости 5 звезд или правильного товара")
                    logger.info(f"[LOG] Отправлено сообщение о необходимости 5 звезд или правильного товара")
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
                activate_extended_warranty(message.chat.id, product_id, msg.message_id, photo.file_id, review_date)
                
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


@disable_ai_mode
def activate_extended_warranty(chat_id, product_id, message_id=None, photo_id=None, review_date=None):
    """Активирует расширенную гарантию для пользователя"""
    try:
        print(f"[LOG] Активация расширенной гарантии для пользователя {chat_id} на товар {product_id}")
        
        product = goods.objects.get(id=product_id)
        user = User.objects.get(telegram_id=chat_id)
        
        # Проверяем, не возвращен ли товар
        if product.is_returned:
            error_text = "Товар возвращен или отменен. Расширенная гарантия недоступна."
            send_long_message(chat_id, error_text, message_id)
            return
        
        warranty_data = user.warranty_data or {}
        if isinstance(warranty_data, str):
            warranty_data = json.loads(warranty_data)
        
        # Инициализируем структуру данных для товара, если её нет
        if str(product_id) not in warranty_data:
            warranty_data[str(product_id)] = {
                'is_active': False,
                'info': {},
                'screenshot': None
            }
        
        # Активируем гарантию
        warranty_data[str(product_id)]['is_active'] = True
        
        # Определяем дату начала гарантии
        if review_date:
            try:
                # Парсим дату из строки
                start_date = timezone.datetime.strptime(review_date, "%d.%m.%Y")
            except ValueError:
                # Если дата некорректная, используем текущую дату
                start_date = timezone.now()
        else:
            # Если дата отзыва не указана, используем текущую дату
            start_date = timezone.now()
            review_date = start_date.strftime("%d.%m.%Y")
        
        # Рассчитываем дату окончания гарантии
        warranty_years = product.extended_warranty
        end_date = start_date + timezone.timedelta(days=int(warranty_years * 365))
        
        # Форматируем даты
        start_date_str = start_date.strftime("%d.%m.%Y")
        end_date_str = end_date.strftime("%d.%m.%Y")
        
        # Форматируем срок гарантии
        if warranty_years.is_integer():
            warranty_text = f"{int(warranty_years)} {'год' if warranty_years == 1 else 'года' if 1 < warranty_years < 5 else 'лет'}"
        else:
            months = int(warranty_years * 12)
            warranty_text = f"{months} {'месяц' if months == 1 else 'месяца' if 1 < months < 5 else 'месяцев'}"
        
        # Сохраняем информацию о товаре
        warranty_info = {
            'name': product.name,
            'activation_date': start_date_str,
            'end_date': end_date_str,
            'warranty_period': warranty_text,
            'review_date': review_date,
            'status': 'Активна'
        }
        warranty_data[str(product_id)]['info'] = warranty_info
        
        # Сохраняем скриншот, если он есть
        if photo_id:
            warranty_data[str(product_id)]['screenshot'] = {
                'photo_id': photo_id,
                'upload_date': timezone.now().strftime("%d.%m.%Y %H:%M:%S")
            }
        
        user.warranty_data = warranty_data
        user.save()

        # Сохраняем информацию в Excel
        excel_handler = WarrantyExcelHandler()
        user_data = {
            'telegram_id': user.telegram_id,
            'user_name': user.user_name
        }
        product_data = {
            'id': product.id,
            'name': product.name
        }
        warranty_info['screenshot_id'] = photo_id
        excel_handler.add_warranty_record(user_data, product_data, warranty_info)
        
        print(f"[LOG] Гарантия активирована для товара {product_id}")
        
        # Формируем сообщение об успешной активации
        success_text = (
            f"✅ Расширенная гарантия успешно активирована!\n\n"
            f"🛡️ Информация о расширенной гарантии на {product.name}:\n"
            f"📅 Дата активации: {start_date_str}\n"
            f"⏳ Срок гарантии: {warranty_text}\n"
            f"📆 Дата окончания: {end_date_str}"
        )
        
        # Создаем клавиатуру с кнопкой возврата
        markup = InlineKeyboardMarkup()
        back_btn = InlineKeyboardButton("⬅️ Вернуться к товару", callback_data=f"product_{product_id}")
        markup.add(back_btn)
        
        # Отправляем сообщение об успешной активации
        send_long_message(chat_id, success_text, message_id, markup)
        
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

@disable_ai_mode
def confirm_review(call: CallbackQuery) -> None:
    """Обработчик для ручного подтверждения скриншота с отзывом"""
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
        product_id = int(parts[2])
        chat_id = call.message.chat.id
        
        print(f"[LOG] Пользователь {chat_id} подтвердил скриншот отзыва для товара {product_id}")
        logger.info(f"[LOG] Пользователь {chat_id} подтвердил скриншот отзыва для товара {product_id}")
        
        # Получаем информацию о скриншоте из состояния
        if chat_id in manual_confirmation_state:
            photo_id = manual_confirmation_state[chat_id].get('photo_id')
            review_date = manual_confirmation_state[chat_id].get('review_date')
            
            # Активируем расширенную гарантию
            activate_extended_warranty(chat_id, product_id, call.message.message_id, photo_id, review_date)
        else:
            # Если состояние не найдено, активируем без скриншота
            activate_extended_warranty(chat_id, product_id, call.message.message_id)
        
    except Exception as e:
        print(f"[ERROR] Ошибка при ручном подтверждении скриншота: {e}")
        logger.error(f"[ERROR] Ошибка при ручном подтверждении скриншота: {e}")
        
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )


@disable_ai_mode
def cancel_review(call: CallbackQuery) -> None:
    """Обработчик для отмены ручного подтверждения скриншота"""
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
        product_id = int(parts[2])
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


@disable_ai_mode
def show_my_warranties(call: CallbackQuery) -> None:
    """Показывает список товаров с активированной расширенной гарантией"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        warranty_data = user.warranty_data or {}
        
        if isinstance(warranty_data, str):
            warranty_data = json.loads(warranty_data)
        
        # Фильтруем только активные гарантии
        active_warranties = {
            product_id: data 
            for product_id, data in warranty_data.items() 
            if data.get('is_active', False)
        }
        
        if not active_warranties:
            # Если нет активированных гарантий
            text = "У вас пока нет активированных расширенных гарантий на товары."
        else:
            # Формируем список товаров с расширенной гарантией
            text = "🛡️ Товары с активированной расширенной гарантией:\n\n"
            current_date = timezone.now().date()
            
            for product_id, data in active_warranties.items():
                try:
                    product_info = data.get('info', {})
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
                        
                        # Проверяем, не возвращен ли товар
                        if product.is_returned:
                            text += (
                                f"❌ Возвращен\n"
                                f"📱 {product.name}\n"
                                f"ℹ️ Товар возвращен или отменен\n\n"
                            )
                            continue
                        
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
                            'warranty_period': warranty_text,
                            'status': 'Активна'
                        }
                        
                        text += (
                            f"✅ Активна\n"
                            f"📱 {product_info['name']}\n"
                            f"⏳ Срок: {product_info['warranty_period']}\n"
                            f"📅 Активация: {product_info['activation_date']}\n"
                            f"📆 Окончание: {product_info['end_date']}\n\n"
                        )
                        
                        # Сохраняем информацию для будущего использования
                        warranty_data[str(product_id)]['info'] = product_info
                except goods.DoesNotExist:
                    continue
            
            # Сохраняем обновленную информацию
            user.warranty_data = warranty_data
            user.save()
        
        markup = InlineKeyboardMarkup()
        warranty_case_btn = InlineKeyboardButton("🛠️ Гарантийный случай", callback_data="warranty_cases")
        back_btn = InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu")
        markup.add(warranty_case_btn)
        markup.add(back_btn)
        
        # Удаляем предыдущее сообщение
        try:
            bot.delete_message(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        except Exception as e:
            print(f"[ERROR] Ошибка при удалении сообщения: {e}")
            logger.error(f"[ERROR] Ошибка при удалении сообщения: {e}")
        
        # Отправляем текст с учетом возможной длины
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

@disable_ai_mode
@bot.callback_query_handler(func=lambda call: call.data.startswith('support_'))
def product_support(call: CallbackQuery) -> None:
    """Обработчик для кнопки поддержки в меню товара"""
    try:
        product_id = int(call.data.split('_')[1])
        product = goods.objects.get(id=product_id)
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Включаем режим ИИ для общения с поддержкой
        user.is_ai = True
        
        # Сохраняем product_id в истории чата для передачи в AI
        chat_history = user.chat_history or {}
        chat_history['product_id'] = product_id
        chat_history['ai_counter'] = 0  # Сбрасываем счетчик
        user.chat_history = chat_history
        user.save()
        
        # Формируем сообщение с учетом AI инструкции товара
        support_text = f"📞 Поддержка по товару: {product.name}\n\nВы можете задать свой вопрос о данном товаре в этот чат."
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=support_text,
            reply_markup=back_to_main_markup
        )
        
        print(f"[LOG] Активирована поддержка для товара {product.name} пользователем {user.telegram_id}")
        logger.info(f"[LOG] Активирована поддержка для товара {product.name} пользователем {user.telegram_id}")
        
    except (goods.DoesNotExist, User.DoesNotExist, ValueError) as e:
        bot.answer_callback_query(call.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")
        logger.error(f"Ошибка в product_support: {e}")

def send_chat_history_to_admin(user: User, chat_history: dict, product_id: int = None):
    """Отправляет историю переписки администратору"""
    try:
        # Получаем всех администраторов
        admin_users = User.objects.filter(is_admin=True)
        
        if not admin_users.exists():
            print("[WARNING] Нет администраторов для отправки уведомления")
            logger.warning("[WARNING] Нет администраторов для отправки уведомления")
            return
        
        # Формируем сообщение с историей переписки
        product_name = "Неизвестный товар"
        if product_id:
            try:
                product = goods.objects.get(id=product_id)
                product_name = product.name
            except goods.DoesNotExist:
                pass
        
        # Получаем историю из AI API
        ai = OpenAIAPI()
        user_chat_history = ai.chat_history.get(str(user.telegram_id), [])
        
        # Формируем текст истории переписки
        history_text = ""
        for message in user_chat_history:
            if message.get('role') == 'user':
                history_text += f"👤 Пользователь: {message.get('content', '')}\n\n"
            elif message.get('role') == 'assistant':
                history_text += f"🤖 AI: {message.get('content', '')}\n\n"
        
        # Ограничиваем длину сообщения
        if len(history_text) > 3000:
            history_text = history_text[:3000] + "...\n\n[История обрезана]"
        
        notification_text = (
            f"🚨 УВЕДОМЛЕНИЕ О ПРЕВЫШЕНИИ ЛИМИТА AI\n\n"
            f"👤 Пользователь: {user.user_name} (@{user.telegram_id})\n"
            f"📱 Товар: {product_name}\n"
            f"⏰ Время: {timezone.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📝 История переписки:\n"
            f"{history_text}"
        )
        
        # Отправляем уведомление всем администраторам
        for admin in admin_users:
            try:
                bot.send_message(
                    chat_id=admin.telegram_id,
                    text=notification_text
                )
                print(f"[LOG] Уведомление отправлено администратору {admin.telegram_id}")
                logger.info(f"[LOG] Уведомление отправлено администратору {admin.telegram_id}")
            except Exception as e:
                print(f"[ERROR] Ошибка отправки уведомления администратору {admin.telegram_id}: {e}")
                logger.error(f"[ERROR] Ошибка отправки уведомления администратору {admin.telegram_id}: {e}")
                
    except Exception as e:
        print(f"[ERROR] Ошибка в send_chat_history_to_admin: {e}")
        logger.error(f"[ERROR] Ошибка в send_chat_history_to_admin: {e}")

def send_chat_history_to_admin_fixed(user: User, chat_history: dict, product_id: int = None):
    """
    Исправленная версия функции для отправки истории переписки администратору.
    Получает историю из базы данных пользователя.
    """
    try:
        # Получаем всех администраторов
        admin_users = User.objects.filter(is_admin=True)
        if not admin_users.exists():
            logger.warning("Нет администраторов для отправки уведомления")
            return
        
        # Получаем название товара
        product_name = "Неизвестный товар"
        if product_id:
            try:
                product = goods.objects.get(id=product_id)
                product_name = product.name
            except goods.DoesNotExist:
                pass
        
        # Получаем историю переписки из базы данных пользователя
        conversation_history = chat_history.get('conversation_history', [])
        
        # Формируем текст истории переписки
        history_text = ""
        if conversation_history:
            for msg in conversation_history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', '')
                
                if role == 'user':
                    history_text += f"👤 Пользователь: {content}\n"
                elif role == 'assistant':
                    history_text += f"🤖 AI: {content}\n"
                
                # Ограничиваем длину сообщения
                if len(history_text) > 3000:
                    history_text = history_text[:3000] + "\n\n... (история обрезана из-за ограничения длины)"
                    break
        else:
            history_text = "История переписки пуста или недоступна.\nВозможно, пользователь достиг лимита до отправки сообщений."
        
        # Формируем сообщение для администратора
        admin_message = f"""🚨 УВЕДОМЛЕНИЕ О ПРЕВЫШЕНИИ ЛИМИТА AI

👤 Пользователь: {user.user_name} (@{user.telegram_id})
📱 Товар: {product_name}
⏰ Время: {timezone.now().strftime('%d.%m.%Y %H:%M')}

📝 История переписки:
{history_text}"""
        
        # Отправляем уведомление всем администраторам
        for admin in admin_users:
            try:
                bot.send_message(admin.telegram_id, admin_message)
                logger.info(f"Уведомление отправлено администратору {admin.telegram_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin.telegram_id}: {e}")
        
        # Очищаем AI историю после отправки уведомления
        ai = OpenAIAPI()
        ai.clear_chat_history(int(user.telegram_id))
        logger.info(f"AI история очищена для пользователя {user.telegram_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в send_chat_history_to_admin_fixed: {e}")

def chat_with_ai(message):
    try:
        # Проверяем, ожидает ли пользователь ввода номера телефона для гарантийного случая
        if message.chat.id in warranty_case_phone_state:
            process_warranty_case_contact(message)
            return
        
        # Проверяем, ожидает ли пользователь ввода описания проблемы для гарантийного случая
        if message.chat.id in warranty_case_description_state:
            process_warranty_case_description(message)
            return

        user = User.objects.get(telegram_id=message.chat.id)
        
        # Проверяем, не является ли сообщение командой или кнопкой меню
        if message.text == "📱 Каталог товаров":
            show_categories(message.chat.id)
            return
        elif message.text == "🛡️ Гарантия":
            show_warranty_main_menu(CallbackQuery(from_user=message.from_user, message=message, data="warranty_main_menu", id=""))
            return
        elif message.text == "🔧 Гарантийный случай":
            show_warranty_cases(CallbackQuery(from_user=message.from_user, message=message, data="warranty_cases", id=""))
            return
        elif message.text == "🔧 Админ-панель":
            handle_admin_panel(message)
            return
        
        # Проверяем, активирован ли режим общения с ИИ
        if not user.is_ai:
            # Если пользователь не в режиме AI, предлагаем перейти к каталогу
            markup = InlineKeyboardMarkup()
            catalog_btn = InlineKeyboardButton("📱 Каталог товаров", callback_data="catalog")
            markup.add(catalog_btn)
            
            bot.send_message(
                chat_id=message.chat.id,
                text="Для получения поддержки выберите товар из каталога и нажмите кнопку 'Поддержка'.",
                reply_markup=markup
            )
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
            # Получаем ID товара для отправки администратору
            product_id = chat_history.get('product_id')
            
            # Отправляем историю переписки администратору
            send_chat_history_to_admin_fixed(user, chat_history, product_id)
            
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
        
        # Получаем ID товара из истории чата
        product_id = chat_history.get('product_id')
        ai_instruction = None
        
        if product_id:
            try:
                product = goods.objects.get(id=product_id)
                # Получаем AI инструкцию для данного товара
                ai_instruction = product.ai_instruction
                print(f"[LOG] Используется AI инструкция для товара {product.name}")
                logger.info(f"[LOG] Используется AI инструкция для товара {product.name}")
            except goods.DoesNotExist:
                pass
        
        response = ai.get_response(message.chat.id, message.text, ai_instruction)
        
        if response and 'message' in response:
            bot.send_message(message.chat.id, response['message'])
            
            # Увеличиваем счетчик сообщений
            chat_history['ai_counter'] = ai_counter + 1
            
            # Сохраняем историю переписки для отправки администратору
            if 'conversation_history' not in chat_history:
                chat_history['conversation_history'] = []
            
            # Добавляем сообщение пользователя и ответ AI
            chat_history['conversation_history'].append({
                'role': 'user',
                'content': message.text,
                'timestamp': timezone.now().isoformat()
            })
            chat_history['conversation_history'].append({
                'role': 'assistant', 
                'content': response['message'],
                'timestamp': timezone.now().isoformat()
            })
            
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

@disable_ai_mode
def back_to_main(call: CallbackQuery) -> None:
    """Обработчик для возврата в главное меню"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        user.is_ai = False
        user.chat_history = {}
        
        # Удаляем предыдущие сообщения
        delete_previous_messages(call.message.chat.id, user)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=MAIN_TEXT,
            reply_markup=main_markup
        )
    except User.DoesNotExist:
        pass

@disable_ai_mode
def back_to_categories(call: CallbackQuery) -> None:
    """Обработчик для возврата к списку категорий"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        # Удаляем предыдущие сообщения
        delete_previous_messages(call.message.chat.id, user)
    except User.DoesNotExist:
        pass
    
    show_categories(call.message.chat.id, call.message.message_id)

@disable_ai_mode
def admin_panel(call: CallbackQuery) -> None:
    """Показывает админ-панель"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        if (user.is_admin==False):
            bot.answer_callback_query(
                callback_query_id=call.id,
                text="У вас нет доступа к админ-панели"
            )
            return
        
        markup = InlineKeyboardMarkup()
        excel_btn = InlineKeyboardButton("📊 Получить Excel-таблицу", callback_data="admin_excel")
        back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(excel_btn)
        markup.add(back_btn)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🔧 Админ-панель\n\nВыберите действие:",
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка при показе админ-панели: {e}")
        logger.error(f"[ERROR] Ошибка при показе админ-панели: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Попробуйте позже."
        )


@disable_ai_mode
def send_excel_to_admin(call: CallbackQuery) -> None:
    """Отправляет Excel-таблицу админу"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        if (user.is_admin==False):
            bot.answer_callback_query(
                callback_query_id=call.id,
                text="У вас нет доступа к админ-панели"
            )
            return
        
        # Отправляем сообщение о начале процесса
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="⏳ Подготовка Excel-таблицы..."
        )
        
        # Получаем путь к файлу Excel
        excel_handler = WarrantyExcelHandler()
        file_path = excel_handler.file_path
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Файл Excel не найден"
            )
            return
        
        # Отправляем файл
        with open(file_path, 'rb') as file:
            bot.send_document(
                chat_id=call.message.chat.id,
                document=file,
                caption="📊 Таблица с данными о гарантиях"
            )
        
        # Возвращаем админ-панель
        admin_panel(call)
        
    except Exception as e:
        print(f"[ERROR] Ошибка при отправке Excel-таблицы: {e}")
        logger.error(f"[ERROR] Ошибка при отправке Excel-таблицы: {e}")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ Произошла ошибка при отправке таблицы: {str(e)}"
        )


@disable_ai_mode
@bot.message_handler(func=lambda message: message.text == "🔧 Админ-панель")
def handle_admin_panel(message: Message) -> None:
    """Обработчик кнопки админ-панели"""
    try:
        user = User.objects.get(telegram_id=message.chat.id)
        if (user.is_admin==False):
            bot.answer_callback_query(
                callback_query_id=message.id,
                text="У вас нет доступа к админ-панели"
            )
            return
        
        markup = InlineKeyboardMarkup()
        excel_btn = InlineKeyboardButton("📊 Получить Excel-таблицу", callback_data="admin_excel")
        back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(excel_btn)
        markup.add(back_btn)
        
        bot.reply_to(
            message,
            "🔧 Админ-панель\n\nВыберите действие:",
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка при показе админ-панели: {e}")
        logger.error(f"[ERROR] Ошибка при показе админ-панели: {e}")
        bot.reply_to(
            message,
            "Произошла ошибка. Попробуйте позже."
        )


@disable_ai_mode
@bot.message_handler(commands=['admin'])
def admin_command(message: Message) -> None:
    """Обработчик команды /admin"""
    try:
        user = User.objects.get(telegram_id=message.chat.id)
        if (user.is_admin==False):
            bot.answer_callback_query(
                callback_query_id=message.id,
                text="У вас нет доступа к админ-панели"
            )
            return
        
        markup = InlineKeyboardMarkup()
        excel_btn = InlineKeyboardButton("📊 Получить Excel-таблицу", callback_data="admin_excel")
        back_btn = InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
        markup.add(excel_btn)
        markup.add(back_btn)
        
        bot.reply_to(
            message,
            "🔧 Админ-панель\n\nВыберите действие:",
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка при показе админ-панели: {e}")
        logger.error(f"[ERROR] Ошибка при показе админ-панели: {e}")
        bot.reply_to(
            message,
            "Произошла ошибка. Попробуйте позже."
        )

@disable_ai_mode
def show_warranty_cases(call: CallbackQuery) -> None:
    user = User.objects.get(telegram_id=call.from_user.id)
    warranty_data = user.warranty_data or {}
    # Собираем все активные гарантии
    active_warranties = []
    for product_id, data in warranty_data.items():
        if data.get('is_active', False):
            try:
                product = goods.objects.get(id=product_id)
                info = data.get('info', {})
                active_warranties.append({
                    'id': product.id,
                    'name': product.name,
                    'activation_date': info.get('activation_date'),
                    'end_date': info.get('end_date'),
                    'warranty_period': info.get('warranty_period'),
                })
            except goods.DoesNotExist:
                continue
    if not active_warranties:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="У вас нет активных расширенных гарантий.",
            reply_markup=back_to_main_markup
        )
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for w in active_warranties:
        markup.add(InlineKeyboardButton(
            text=f"{w['name']}",
            callback_data=f"atwarranty_case_{w['id']}"
        ))
    markup.add(InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu"))
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Если у вас возникла проблема с товаром, то выберите с каким из выпадающего списка.",
        reply_markup=markup
    )

@disable_ai_mode
def handle_warranty_case(call: CallbackQuery) -> None:
    """Обрабатывает выбор товара для гарантийного случая"""
    try:
        # Получаем ID товара из callback_data
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
            
        product_id = int(parts[2])
        user = User.objects.get(telegram_id=call.from_user.id)
        product = goods.objects.get(id=product_id)
        
        print(f"[LOG] Запрос гарантийного случая от пользователя {user.telegram_id} для товара {product.name}")
        logger.info(f"[LOG] Запрос гарантийного случая от пользователя {user.telegram_id} для товара {product.name}")
        
        # Сохраняем состояние ожидания номера телефона
        warranty_case_phone_state[call.from_user.id] = {
            'product_id': product_id,
            'message_id': call.message.message_id,
            'waiting_for_phone': True
        }
        
        # Создаем клавиатуру с кнопкой для отправки контакта
        markup = InlineKeyboardMarkup()
        # Добавляем кнопку для отправки контакта (будет работать только в личных сообщениях)
        share_contact_btn = InlineKeyboardButton(
            "📞 Поделиться номером телефона", 
            callback_data=f"request_contact_{product_id}"
        )
        cancel_btn = InlineKeyboardButton("❌ Отменить", callback_data="back_to_main")
        markup.add(share_contact_btn)
        markup.add(cancel_btn)
        
        # Запрашиваем номер телефона
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"📞 Для обработки гарантийного случая по товару '{product.name}' "
                f"нам нужен ваш номер телефона для связи.\n\n"
                f"Пожалуйста, нажмите кнопку ниже или отправьте ваш номер телефона в формате:\n"
                f"+7 (999) 123-45-67"
            ),
            reply_markup=markup
        )
        
        print(f"[LOG] Запрошен номер телефона у пользователя {user.telegram_id}")
        logger.info(f"[LOG] Запрошен номер телефона у пользователя {user.telegram_id}")
        
    except (ValueError, goods.DoesNotExist) as e:
        print(f"[ERROR] Ошибка при обработке гарантийного случая: {e}")
        logger.error(f"[ERROR] Ошибка при обработке гарантийного случая: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

@disable_ai_mode
def send_instruction_pdf(call: CallbackQuery, bot: TeleBot) -> None:
    """Отправляет PDF файл инструкции"""
    try:
        instruction_id = int(call.data.split('_')[-1])
        instruction = FAQ.objects.get(id=instruction_id, is_active=True)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_instructions_{instruction.product.id}"))
        
        if instruction.pdf_file:
            with open(instruction.pdf_file.path, 'rb') as pdf:
                caption = f"📖 {instruction.title}"
                if instruction.description:
                    caption += f"\n\n{instruction.description}"
                
                bot.send_document(
                    chat_id=call.message.chat.id,
                    document=pdf,
                    caption=caption,
                    reply_markup=markup
                )
        else:
            text = f"📖 {instruction.title}\n\nПDF файл не найден."
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                reply_markup=markup
            )
    except (ValueError, FAQ.DoesNotExist):
        # Если произошла ошибка, возвращаемся к списку товаров
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Ошибка: Инструкция не найдена."
        )

@disable_ai_mode
def send_faq_pdf(call: CallbackQuery, bot: TeleBot) -> None:
    """Отправляет PDF файл FAQ"""
    try:
        faq_id = int(call.data.split('_')[-1])
        faq = FAQ.objects.get(id=faq_id, is_active=True)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_faq_{faq.product.id}"))
        
        if faq.pdf_file:
            with open(faq.pdf_file.path, 'rb') as pdf:
                caption = f"❓ {faq.title}"
                if faq.description:
                    caption += f"\n\n{faq.description}"
                
                bot.send_document(
                    chat_id=call.message.chat.id,
                    document=pdf,
                    caption=caption,
                    reply_markup=markup
                )
        else:
            text = f"❓ {faq.title}\n\nПDF файл не найден."
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                reply_markup=markup
            )
    except (ValueError, FAQ.DoesNotExist):
        # Если произошла ошибка, возвращаемся к списку товаров
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Ошибка: FAQ не найден."
        )

@disable_ai_mode
def request_contact_for_warranty(call: CallbackQuery) -> None:
    """Запрашивает контакт пользователя для гарантийного случая"""
    try:
        parts = call.data.split('_')
        if len(parts) != 3:
            raise ValueError("Неверный формат callback_data")
        
        product_id = int(parts[2])
        
        # Создаем клавиатуру с кнопкой запроса контакта
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        contact_btn = KeyboardButton("📞 Поделиться номером телефона", request_contact=True)
        cancel_btn = KeyboardButton("❌ Отменить")
        markup.add(contact_btn)
        markup.add(cancel_btn)
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Нажмите кнопку ниже, чтобы поделиться вашим номером телефона:",
            reply_markup=markup
        )
        
        print(f"[LOG] Запрошен контакт у пользователя {call.from_user.id}")
        logger.info(f"[LOG] Запрошен контакт у пользователя {call.from_user.id}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при запросе контакта: {e}")
        logger.error(f"[ERROR] Ошибка при запросе контакта: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")

@disable_ai_mode
def process_warranty_case_contact(message) -> None:
    """Обрабатывает полученный контакт для гарантийного случая"""
    try:
        user_id = message.chat.id
        
        # Проверяем, ожидаем ли мы номер телефона от этого пользователя
        if user_id not in warranty_case_phone_state:
            return
        
        phone_number = None
        
        # Получаем номер телефона из контакта или текста
        if hasattr(message, 'contact') and message.contact:
            phone_number = message.contact.phone_number
            print(f"[LOG] Получен контакт от пользователя {user_id}: {phone_number}")
        elif hasattr(message, 'text') and message.text:
            # Проверяем, не является ли это отменой
            if message.text == "❌ Отменить":
                # Удаляем состояние и возвращаемся в главное меню
                del warranty_case_phone_state[user_id]
                from bot.keyboards import main_markup
                bot.send_message(
                    chat_id=user_id,
                    text="Операция отменена.",
                    reply_markup=main_markup
                )
                return
            
            # Пытаемся извлечь номер телефона из текста
            import re
            # Паттерн для российских номеров
            phone_pattern = r'(\+?7|8)?[\s\-\(\)]?(\d{3})[\s\-\(\)]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})'
            match = re.search(phone_pattern, message.text)
            if match:
                # Формируем номер в стандартном формате
                groups = match.groups()
                if groups[0] in ['8', None]:
                    phone_number = f"+7{groups[1]}{groups[2]}{groups[3]}{groups[4]}"
                else:
                    phone_number = f"+7{groups[1]}{groups[2]}{groups[3]}{groups[4]}"
                print(f"[LOG] Извлечен номер телефона из текста: {phone_number}")
            else:
                bot.send_message(
                    chat_id=user_id,
                    text="Неверный формат номера телефона. Пожалуйста, отправьте номер в формате +7 (999) 123-45-67 или используйте кнопку для отправки контакта."
                )
                return
        
        if not phone_number:
            bot.send_message(
                chat_id=user_id,
                text="Не удалось получить номер телефона. Пожалуйста, попробуйте еще раз."
            )
            return
        
        # Получаем информацию о пользователе и товаре
        state_data = warranty_case_phone_state[user_id]
        product_id = state_data['product_id']
        
        user = User.objects.get(telegram_id=user_id)
        product = goods.objects.get(id=product_id)
        
        # Сохраняем номер телефона пользователя
        user.phone_number = phone_number
        user.save()
        
        # Удаляем состояние ожидания номера телефона
        del warranty_case_phone_state[user_id]
        
        # Устанавливаем состояние ожидания описания проблемы
        warranty_case_description_state[user_id] = {
            'product_id': product_id,
            'phone_number': phone_number,
            'waiting_for_description': True
        }
        
        # Убираем специальную клавиатуру и запрашиваем описание проблемы
        from bot.keyboards import main_markup
        markup = InlineKeyboardMarkup()
        cancel_btn = InlineKeyboardButton("❌ Отменить", callback_data="back_to_main")
        markup.add(cancel_btn)
        
        bot.send_message(
            chat_id=user_id,
            text=(
                f"📞 Номер телефона получен: {phone_number}\n\n"
                f"📝 Теперь, пожалуйста, кратко опишите проблему с товаром '{product.name}':\n\n"
                f"Например:\n"
                f"• Не включается\n"
                f"• Сломался через неделю использования\n"
                f"• Не работает как заявлено\n"
                f"• Брак или дефект"
            ),
            reply_markup=markup
        )
        
        print(f"[LOG] Запрошено описание проблемы у пользователя {user_id}")
        logger.info(f"[LOG] Запрошено описание проблемы у пользователя {user_id}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке контакта для гарантийного случая: {e}")
        logger.error(f"[ERROR] Ошибка при обработке контакта для гарантийного случая: {e}")
        
        # Удаляем состояние ожидания в случае ошибки
        if user_id in warranty_case_phone_state:
            del warranty_case_phone_state[user_id]
        
        from bot.keyboards import main_markup
        bot.send_message(
            chat_id=user_id,
            text="Произошла ошибка при обработке заявки. Пожалуйста, попробуйте позже.",
            reply_markup=main_markup
        )

@disable_ai_mode
def process_warranty_case_description(message) -> None:
    """Обрабатывает описание проблемы для гарантийного случая"""
    try:
        user_id = message.chat.id
        
        # Проверяем, ожидаем ли мы описание проблемы от этого пользователя
        if user_id not in warranty_case_description_state:
            return
        
        # Проверяем, не является ли это отменой
        if hasattr(message, 'text') and message.text == "❌ Отменить":
            # Удаляем состояние и возвращаемся в главное меню
            del warranty_case_description_state[user_id]
            from bot.keyboards import main_markup
            bot.send_message(
                chat_id=user_id,
                text="Операция отменена.",
                reply_markup=main_markup
            )
            return
        
        # Получаем описание проблемы
        if not hasattr(message, 'text') or not message.text:
            bot.send_message(
                chat_id=user_id,
                text="Пожалуйста, отправьте текстовое описание проблемы."
            )
            return
        
        problem_description = message.text.strip()
        
        # Ограничиваем длину описания
        if len(problem_description) > 500:
            bot.send_message(
                chat_id=user_id,
                text="Описание слишком длинное. Пожалуйста, опишите проблему кратко (до 500 символов)."
            )
            return
        
        if len(problem_description) < 5:
            bot.send_message(
                chat_id=user_id,
                text="Описание слишком короткое. Пожалуйста, опишите проблему более подробно."
            )
            return
        
        # Получаем информацию из состояния
        state_data = warranty_case_description_state[user_id]
        product_id = state_data['product_id']
        phone_number = state_data['phone_number']
        
        user = User.objects.get(telegram_id=user_id)
        product = goods.objects.get(id=product_id)
        
        # Получаем скриншот отзыва пользователя для данного товара
        warranty_data = user.warranty_data or {}
        product_warranty = warranty_data.get(str(product_id), {})
        screenshot_data = product_warranty.get('screenshot')
        
        # Получаем контакт администратора
        admin_contact = AdminContact.objects.filter(is_active=True).first()
        
        # Отправляем уведомление админам
        admin_users = User.objects.filter(is_admin=True)
        for admin in admin_users:
            admin_message = (
                f"⚠️ Новый гарантийный случай!\n\n"
                f"👤 Пользователь: {user.user_name}\n"
                f"📱 Товар: {product.name}\n"
                f"📞 Телефон: {phone_number}\n"
                f"🆔 ID пользователя: {user.telegram_id}\n"
                f"📝 Описание проблемы:\n{problem_description}\n"
            )
            
            if hasattr(message, 'from_user') and message.from_user.username:
                admin_message += f"📨 Telegram: @{message.from_user.username}\n"
            
            # Отправляем основную информацию
            sent_message = bot.send_message(
                chat_id=admin.telegram_id,
                text=admin_message
            )
            
            # Если есть скриншот отзыва, отправляем его отдельно
            if screenshot_data and screenshot_data.get('photo_id'):
                try:
                    bot.send_photo(
                        chat_id=admin.telegram_id,
                        photo=screenshot_data['photo_id'],
                        caption=f"📸 Скриншот отзыва для верификации гарантии\n"
                               f"📅 Дата загрузки: {screenshot_data.get('upload_date', 'Не указана')}"
                    )
                    print(f"[LOG] Отправлен скриншот отзыва админу {admin.telegram_id}")
                except Exception as e:
                    print(f"[ERROR] Ошибка при отправке скриншота админу: {e}")
                    logger.error(f"[ERROR] Ошибка при отправке скриншота админу: {e}")
        
        # Удаляем состояние ожидания
        del warranty_case_description_state[user_id]
        
        # Отправляем подтверждение пользователю
        from bot.keyboards import main_markup
        confirmation_message = (
            f"✅ Ваша заявка на гарантийный случай принята!\n\n"
            f"📱 Товар: {product.name}\n"
            f"📞 Контактный телефон: {phone_number}\n"
            f"📝 Описание проблемы: {problem_description}\n\n"
            f"Администратор скоро свяжется с вами.\n\n"
            f"Контакт администратора:\n{admin_contact.admin_contact if admin_contact else 'Не указан'}"
        )
        
        bot.send_message(
            chat_id=user_id,
            text=confirmation_message,
            reply_markup=main_markup
        )
        
        print(f"[LOG] Гарантийный случай обработан для пользователя {user_id}, товар {product.name}")
        logger.info(f"[LOG] Гарантийный случай обработан для пользователя {user_id}, товар {product.name}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке описания проблемы: {e}")
        logger.error(f"[ERROR] Ошибка при обработке описания проблемы: {e}")
        
        # Удаляем состояние ожидания в случае ошибки
        if user_id in warranty_case_description_state:
            del warranty_case_description_state[user_id]
        
        from bot.keyboards import main_markup
        bot.send_message(
            chat_id=user_id,
            text="Произошла ошибка при обработке заявки. Пожалуйста, попробуйте позже.",
            reply_markup=main_markup
        )

@disable_ai_mode
def show_warranty_main_menu(call: CallbackQuery) -> None:
    """Показывает главное меню гарантии"""
    try:
        # Проверяем, есть ли у пользователя активированные гарантии
        has_active_warranties = False
        try:
            user = User.objects.get(telegram_id=call.message.chat.id)
            warranty_data = user.warranty_data or {}
            
            if isinstance(warranty_data, str):
                warranty_data = json.loads(warranty_data)
            
            # Фильтруем только активные гарантии
            active_warranties = {
                product_id: data 
                for product_id, data in warranty_data.items() 
                if data.get('is_active', False)
            }
            
            has_active_warranties = len(active_warranties) > 0
        except User.DoesNotExist:
            pass
        
        markup = get_warranty_main_menu_markup(has_active_warranties)
        text = "🛡️ Раздел гарантии\n\nВыберите нужный вам пункт:"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка при показе главного меню гарантии: {e}")
        logger.error(f"[ERROR] Ошибка при показе главного меню гарантии: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

@disable_ai_mode
def show_warranty_conditions(call: CallbackQuery) -> None:
    """Показывает условия гарантии"""
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=WARRANTY_CONDITIONS_TEXT,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка при показе условий гарантии: {e}")
        logger.error(f"[ERROR] Ошибка при показе условий гарантии: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

@disable_ai_mode
def show_warranty_activation_menu(call: CallbackQuery) -> None:
    """Показывает меню активации расширенной гарантии - список товаров"""
    try:
        # Получаем все активные товары
        products = goods.objects.filter(is_active=True)
        
        if not products.exists():
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu"))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="В настоящее время нет доступных товаров для активации расширенной гарантии.",
                reply_markup=markup
            )
            return
        
        # Группируем товары по категориям
        categories = goods_category.objects.filter(goods__in=products).distinct()
        
        markup = InlineKeyboardMarkup()
        
        if categories.exists():
            markup.add(InlineKeyboardButton("📱 Выбрать по категориям", callback_data="catalog"))
        
        # Добавляем кнопку назад
        markup.add(InlineKeyboardButton("⬅️ Назад к гарантии", callback_data="warranty_main_menu"))
        
        text = (
            "✅ Активация расширенной гарантии\n\n"
            "Для активации расширенной гарантии:\n"
            "1️⃣ Выберите товар из каталога\n"
            "2️⃣ Перейдите в раздел 'Гарантия' товара\n"
            "3️⃣ Следуйте инструкциям для активации\n\n"
            "Выберите способ поиска товара:"
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=markup
        )
        
    except Exception as e:
        print(f"[ERROR] Ошибка при показе меню активации гарантии: {e}")
        logger.error(f"[ERROR] Ошибка при показе меню активации гарантии: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )

@disable_ai_mode
def send_product_instruction_pdf(call: CallbackQuery) -> None:
    """Отправляет PDF файл инструкции товара через ProductDocument"""
    try:
        product_id = int(call.data.split('_')[-1])
        product = goods.objects.get(id=product_id)
        instruction_doc = product.documents.filter(document_type='instructions').first()
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"product_{product_id}"))
        
        if instruction_doc and instruction_doc.pdf_file:
            with open(instruction_doc.pdf_file.path, 'rb') as pdf:
                caption = f"📖 Инструкция по применению {product.name}"
                
                bot.send_document(
                    chat_id=call.message.chat.id,
                    document=pdf,
                    caption=caption,
                    reply_markup=markup
                )
        else:
            text = f"📖 Инструкция для товара {product.name}\n\nПDF файл не найден."
            bot.send_message(
                chat_id=call.message.chat.id,
                text=text,
                reply_markup=markup
            )
    except (ValueError, goods.DoesNotExist):
        # Если произошла ошибка, возвращаемся к списку товаров
        bot.send_message(
            chat_id=call.message.chat.id,
            text="Ошибка: Товар не найден."
        )
