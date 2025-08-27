from traceback import format_exc

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from telebot.apihelper import ApiTelegramException
from telebot.types import Update, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot, logger
from bot.cron import reset_screenshot_counters
from bot.utils.excel_handler import WarrantyExcelHandler

# Импортируем все обработчики из handlers/__init__.py
from bot.handlers import (
    start, menu_call, back_to_main, 
    show_categories, show_category_products, show_product_menu, show_product_info,
    chat_with_ai, activate_warranty, back_to_categories,
    cancel_warranty_activation, show_my_warranties, check_screenshot,
    confirm_review, cancel_review, send_excel_to_admin, admin_command,
    show_warranty_cases, handle_warranty_case, send_instruction_pdf,
    send_product_instruction_pdf,
    request_contact_for_warranty, process_warranty_case_contact,
    show_warranty_main_menu, show_warranty_conditions, show_warranty_activation_menu,
    waranty_goods_fast, support_main_menu, support_ozon, support_wildberries
)


@require_GET
def set_webhook(request: HttpRequest) -> JsonResponse:
    """Setting webhook."""
    bot.set_webhook(url=f"{settings.HOOK}/bot/{settings.BOT_TOKEN}")
    bot.send_message(settings.OWNER_ID, "webhook set")
    return JsonResponse({"message": "OK"}, status=200)


@require_GET
def status(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"message": "OK"}, status=200)


@require_GET
def run_reset_screenshot_counters(request: HttpRequest) -> JsonResponse:
    """
    Ручной запуск задачи сброса счетчиков скриншотов
    Эндпоинт может вызываться внешним cron-сервисом для регулярного запуска
    """
    # Проверка секретного ключа для безопасности
    secret_key = request.GET.get('key', '')
    if secret_key != settings.CRON_SECRET_KEY:
        return JsonResponse({"message": "Unauthorized"}, status=403)
    
    try:
        result = reset_screenshot_counters()
        return JsonResponse({"message": "OK", "result": result}, status=200)
    except Exception as e:
        logger.error(f"Error running reset_screenshot_counters: {e}")
        return JsonResponse({"message": "Error", "error": str(e)}, status=500)


@csrf_exempt
@require_POST
@sync_to_async
def index(request: HttpRequest) -> JsonResponse:
    if request.META.get("CONTENT_TYPE") != "application/json":
        return JsonResponse({"message": "Bad Request"}, status=403)

    json_string = request.body.decode("utf-8")
    update = Update.de_json(json_string)
    try:
        bot.process_new_updates([update])
    except ApiTelegramException as e:
        logger.error(f"Telegram exception. {e} {format_exc()}")
    except ConnectionError as e:
        logger.error(f"Connection error. {e} {format_exc()}")
    except Exception as e:
        bot.send_message(settings.OWNER_ID, f'Error from index: {e}')
        logger.error(f"Unhandled exception. {e} {format_exc()}")
    return JsonResponse({"message": "OK"}, status=200)


"""Common"""

start = bot.message_handler(commands=["start"])(start)
menu_call = bot.callback_query_handler(lambda c: c.data == "menu")(menu_call)
back_to_main_handler = bot.callback_query_handler(lambda c: c.data == "back_to_main")(back_to_main)
my_warranties_handler = bot.callback_query_handler(lambda c: c.data == "my_warranties")(show_my_warranties)
admin_command_handler = bot.message_handler(commands=['admin'])(admin_command)

# Обработчик для контактов и номеров телефона в гарантийных случаях
contact_handler = bot.message_handler(content_types=['contact'])(process_warranty_case_contact)

# Явный обработчик для фотографий
photo_handler = bot.message_handler(content_types=['photo'])(check_screenshot)

# Общий обработчик сообщений (должен идти после специализированных обработчиков)
text_handler = bot.message_handler(func=lambda message: True)(chat_with_ai)

# Обработчики для категорий и товаров
catalog_handler = bot.callback_query_handler(lambda c: c.data == "catalog")(lambda c: show_categories(c.message.chat.id, c.message.message_id))
category_handler = bot.callback_query_handler(lambda c: c.data.startswith("category_"))(show_category_products)
product_handler = bot.callback_query_handler(lambda c: c.data.startswith("product_"))(show_product_menu)
back_to_categories_handler = bot.callback_query_handler(lambda c: c.data == "back_to_categories")(back_to_categories)

# Обработчики для информации о товаре
instructions_handler = bot.callback_query_handler(lambda c: c.data.startswith("instructions_"))(show_product_info)
faq_handler = bot.callback_query_handler(lambda c: c.data.startswith("faq_"))(show_product_info)
warranty_info_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_") and not c.data.startswith("warranty_main") and not c.data.startswith("warranty_conditions") and not c.data.startswith("warranty_activation") and c.data != "warranty_cases")(show_product_info)
support_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_") and c.data.split('_')[1].isdigit())(show_product_info)

# Обработчики для расширенной гарантии
activate_warranty_handler = bot.callback_query_handler(lambda c: c.data.startswith("activate_warranty_"))(activate_warranty)
cancel_warranty_handler = bot.callback_query_handler(lambda c: c.data.startswith("cancel_warranty_"))(cancel_warranty_activation)

# Обработчики для подтверждения скриншотов отзывов
confirm_review_handler = bot.callback_query_handler(lambda c: c.data.startswith("confirm_review_"))(confirm_review)
cancel_review_handler = bot.callback_query_handler(lambda c: c.data.startswith("cancel_review_"))(cancel_review)

# Обработчики для админ-панели
admin_excel_handler = bot.callback_query_handler(lambda c: c.data == "admin_excel")(send_excel_to_admin)

# Обработчики для гарантийных случаев
warranty_cases_handler = bot.callback_query_handler(lambda c: c.data == "warranty_cases")(show_warranty_cases)
warranty_case_handler = bot.callback_query_handler(lambda c: c.data.startswith("atwarranty_case_"))(handle_warranty_case)

# Обработчики для запроса контакта в гарантийном случае
request_contact_handler = bot.callback_query_handler(lambda c: c.data.startswith("request_contact_"))(request_contact_for_warranty)

# Обработчики для PDF инструкций
instruction_pdf_handler = bot.callback_query_handler(lambda c: c.data.startswith("instruction_pdf_"))(send_instruction_pdf)
product_instruction_pdf_handler = bot.callback_query_handler(lambda c: c.data.startswith("product_instruction_pdf_"))(send_product_instruction_pdf)

# Новые обработчики для меню гарантии
warranty_main_menu_handler = bot.callback_query_handler(lambda c: c.data == "warranty_main_menu")(show_warranty_main_menu)
warranty_conditions_handler = bot.callback_query_handler(lambda c: c.data == "warranty_conditions")(show_warranty_conditions)
warranty_activation_menu_handler = bot.callback_query_handler(lambda c: c.data == "warranty_activation_menu")(show_warranty_activation_menu)

# Обработчик для быстрой активации гарантии
warranty_goods_fast_handler = bot.callback_query_handler(lambda c: c.data == "waranty_goods_fast")(waranty_goods_fast)

# Обработчики для поддержки
support_main_handler = bot.callback_query_handler(lambda c: c.data == "help_main")(support_main_menu)
support_ozon_handler = bot.callback_query_handler(lambda c: c.data == "help_ozon")(support_ozon)
support_wildberries_handler = bot.callback_query_handler(lambda c: c.data == "help_wildberries")(support_wildberries)

