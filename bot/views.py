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
    waranty_goods_fast, support_main_menu, support_ozon, support_wildberries,
    warranty_case_platform_choice, warranty_case_ozon, warranty_case_wildberries
)

# Импортируем новые функции поддержки
from bot.handlers.support import (
    show_support_menu, start_support_ozon, start_support_wildberries,
    close_support_ticket, accept_support_ticket, finish_ticket_processing,
    view_ticket_details, already_assigned_callback,
    show_user_tickets, show_user_ticket_actions, user_close_ticket, user_open_ticket,
    decline_support_ticket, admin_list_open_tickets, admin_start_broadcast, admin_broadcast_confirm,
    admin_list_my_tickets, admin_list_in_progress_tickets, takeover_support_ticket, send_ticket_files_to_admin,
    send_all_ticket_files_to_admin,
    admin_back_to_tickets,
    send_broadcast_to_all_users,
    support_start, support_select_category, support_select_product, support_select_issue,
    support_helped, support_not_helped, support_other
)
from bot.handlers.promocodes import (
    promocode_menu, promocode_add, promocode_list, promocode_detail,
    promocode_toggle, promocode_delete, get_user_promocode,
    promocode_select_category, user_select_category,
    handle_promocode_text, handle_promocode_document, promocode_select_category_file,
    promocode_choose_actions, promocode_back_to_category, promocode_state
)


@require_GET
def set_webhook(request: HttpRequest) -> JsonResponse:
    """Setting webhook."""
    try:
        hook_base = (settings.HOOK or '').strip() if hasattr(settings, 'HOOK') else ''
        token = (settings.BOT_TOKEN or '').strip() if hasattr(settings, 'BOT_TOKEN') else ''
        if not hook_base or not token:
            return JsonResponse({
                "message": "Ошибка",
                "detail": "Переменные окружения HOOK или BOT_TOKEN не заданы"
            }, status=400)
        if not hook_base.startswith('http://') and not hook_base.startswith('https://'):
            return JsonResponse({
                "message": "Ошибка",
                "detail": "HOOK должен начинаться с http(s)://"
            }, status=400)

        webhook_url = f"{hook_base}/bot/{token}"
        # Сначала удалим старый вебхук
        try:
            bot.remove_webhook()
        except Exception:
            pass
        # Установим новый вебхук
        bot.set_webhook(url=webhook_url)
        try:
            if settings.OWNER_ID:
                bot.send_message(settings.OWNER_ID, f"✅ Webhook установлен: {webhook_url}")
        except Exception:
            pass
        return JsonResponse({"message": "OK", "webhook": webhook_url}, status=200)
    except ApiTelegramException as e:
        return JsonResponse({
            "message": "Ошибка Telegram",
            "detail": str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "message": "Внутренняя ошибка",
            "detail": str(e)
        }, status=500)


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

# Роутер медиа: если пользователь в поддержке, отправляем в тикет; иначе оставляем прежнее поведение (фото -> гарантия)
def support_media_router(message):
    try:
        # Сначала проверяем, не загружает ли пользователь промокоды
        from bot.handlers.promocodes import promocode_state, handle_promocode_document
        if message.chat.id in promocode_state and promocode_state[message.chat.id].get("awaiting_promocodes"):
            if handle_promocode_document(message):
                return
        
        from bot.handlers.support import support_state, handle_support_message
        if message.chat.id in support_state:
            handle_support_message(message)
            return
        # Если не в поддержке и это фото — передаем в гарантийный обработчик
        if getattr(message, 'photo', None):
            from bot.handlers.common import check_screenshot as cs
            cs(message)
    except Exception:
        # На случай любой ошибки — не ломаем оставшиеся хендлеры
        pass

support_media_handler = bot.message_handler(content_types=['photo','video','document'])(support_media_router)

# Явный обработчик для фотографий (остается на случай, когда не активна поддержка)
photo_handler = bot.message_handler(content_types=['photo'])(check_screenshot)

# Приоритетные обработчики для поддержки
from bot.handlers.support import admin_response_state, support_state, handle_admin_response, handle_support_message

# 1) Текст пользователя в режиме поддержки – сразу в обработчик поддержки
support_text_handler = bot.message_handler(func=lambda m: m.chat.id in support_state, content_types=['text'])(handle_support_message)

# 2) Текст админа в режиме ответа – сразу пользователю
admin_text_response_handler = bot.message_handler(func=lambda m: m.chat.id in admin_response_state, content_types=['text'])(handle_admin_response)

# Обработчики загрузки промокодов (текст/файл) при активном состоянии добавления
promocode_text_handler = bot.message_handler(func=lambda m: (m.chat.id in promocode_state) and bool(promocode_state.get(m.chat.id, {}).get("awaiting_promocodes")), content_types=['text'])(handle_promocode_text)
promocode_document_handler = bot.message_handler(func=lambda m: (m.chat.id in promocode_state) and bool(promocode_state.get(m.chat.id, {}).get("awaiting_promocodes")), content_types=['document'])(handle_promocode_document)

# Общий обработчик сообщений (должен идти после специализированных обработчиков)
text_handler = bot.message_handler(func=lambda message: True)(chat_with_ai)

# Обработчики для категорий и товаров
catalog_handler = bot.callback_query_handler(lambda c: c.data == "catalog")(lambda c: show_categories(c.message.chat.id, c.message.message_id))
category_handler = bot.callback_query_handler(lambda c: c.data.startswith("category_"))(show_category_products)
product_handler = bot.callback_query_handler(lambda c: c.data.startswith("product_"))(show_product_menu)
back_to_categories_handler = bot.callback_query_handler(lambda c: c.data == "back_to_categories")(back_to_categories)

# Новые обработчики для системы гарантийных обращений (ДОЛЖНЫ БЫТЬ ПЕРЕД warranty_info_handler!)
from bot.handlers.warranty import (
    warranty_start, warranty_select_category, warranty_select_product,
    warranty_select_issue, warranty_helped, warranty_not_helped, warranty_other
)

warranty_start_handler = bot.callback_query_handler(lambda c: c.data == "warranty_start")(warranty_start)
warranty_category_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_category_"))(warranty_select_category)
warranty_product_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_product_"))(warranty_select_product)
warranty_issue_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_issue_"))(warranty_select_issue)
warranty_helped_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_helped_"))(warranty_helped)
warranty_not_helped_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_not_helped_"))(warranty_not_helped)
warranty_other_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_other_"))(warranty_other)

# Обработчики для информации о товаре
instructions_handler = bot.callback_query_handler(lambda c: c.data.startswith("instructions_"))(show_product_info)
faq_handler = bot.callback_query_handler(lambda c: c.data.startswith("faq_"))(show_product_info)
warranty_info_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_") and not c.data.startswith("warranty_main") and not c.data.startswith("warranty_conditions") and not c.data.startswith("warranty_activation") and not c.data.startswith("warranty_case") and c.data != "warranty_cases" and c.data != "warranty_start" and not c.data.startswith("warranty_category_") and not c.data.startswith("warranty_product_") and not c.data.startswith("warranty_issue_") and not c.data.startswith("warranty_helped_") and not c.data.startswith("warranty_not_helped_") and not c.data.startswith("warranty_other_"))(show_product_info)
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

# Обработчики для новой системы поддержки
# support_main_handler = bot.callback_query_handler(lambda c: c.data == "help_main")(show_support_menu)  # Устарел, заменен на support_start
support_ozon_handler = bot.callback_query_handler(lambda c: c.data == "support_ozon")(start_support_ozon)
support_wildberries_handler = bot.callback_query_handler(lambda c: c.data == "support_wildberries")(start_support_wildberries)

# Новые обработчики для системы поддержки (аналог гарантийных)
support_start_handler = bot.callback_query_handler(lambda c: c.data == "support_start")(support_start)
support_category_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_category_"))(support_select_category)
support_product_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_product_"))(support_select_product)
support_issue_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_issue_"))(support_select_issue)
support_helped_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_helped_"))(support_helped)
support_not_helped_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_not_helped_"))(support_not_helped)
support_other_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_other_"))(support_other)
close_ticket_handler = bot.callback_query_handler(lambda c: c.data == "close_ticket")(close_support_ticket)
accept_ticket_handler = bot.callback_query_handler(lambda c: c.data.startswith("accept_ticket_"))(accept_support_ticket)
finish_ticket_handler = bot.callback_query_handler(lambda c: c.data.startswith("finish_ticket_"))(finish_ticket_processing)
view_ticket_handler = bot.callback_query_handler(lambda c: c.data.startswith("view_ticket_"))(view_ticket_details)
takeover_ticket_handler = bot.callback_query_handler(lambda c: c.data.startswith("takeover_ticket_"))(takeover_support_ticket)
get_ticket_files_handler = bot.callback_query_handler(lambda c: c.data.startswith("get_ticket_files_"))(send_ticket_files_to_admin)
get_all_ticket_files_handler = bot.callback_query_handler(lambda c: c.data.startswith("get_all_ticket_files_"))(send_all_ticket_files_to_admin)
already_assigned_handler = bot.callback_query_handler(lambda c: c.data == "already_assigned")(already_assigned_callback)

# Пользовательские обращения
support_my_tickets_handler = bot.callback_query_handler(lambda c: c.data == "support_my_tickets")(show_user_tickets)
support_ticket_actions_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_ticket_"))(show_user_ticket_actions)
support_user_close_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_close_"))(user_close_ticket)
support_user_open_handler = bot.callback_query_handler(lambda c: c.data.startswith("support_open_"))(user_open_ticket)

# Отказ админа от обращения после просмотра
support_admin_decline_handler = bot.callback_query_handler(lambda c: c.data.startswith("decline_ticket_"))(decline_support_ticket)

# Админ: список свободных активных обращений
admin_open_tickets_handler = bot.callback_query_handler(lambda c: c.data == "admin_open_tickets")(admin_list_open_tickets)
admin_in_progress_tickets_handler = bot.callback_query_handler(lambda c: c.data == "admin_in_progress_tickets")(admin_list_in_progress_tickets)
from bot.handlers.common import admin_panel as admin_panel_cb
admin_panel_back_handler = bot.callback_query_handler(lambda c: c.data == "admin_panel")(admin_panel_cb)
admin_my_tickets_handler = bot.callback_query_handler(lambda c: c.data == "admin_my_tickets")(admin_list_my_tickets)

# Админ: назад к списку его обращений
admin_back_to_tickets_handler = bot.callback_query_handler(lambda c: c.data == "admin_back_to_tickets")(admin_back_to_tickets)

# Админ: рассылка
admin_broadcast_start_handler = bot.callback_query_handler(lambda c: c.data == "admin_broadcast")(admin_start_broadcast)
broadcast_confirm_handler = bot.callback_query_handler(lambda c: c.data in ("broadcast_confirm", "broadcast_cancel"))(admin_broadcast_confirm)

# Админ: промокоды
promocode_menu_handler = bot.callback_query_handler(lambda c: c.data == "promocode_menu")(promocode_menu)
promocode_add_handler = bot.callback_query_handler(lambda c: c.data == "promocode_add")(promocode_add)
promocode_list_handler = bot.callback_query_handler(lambda c: c.data == "promocode_list")(promocode_list)
promocode_detail_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_detail_"))(promocode_detail)
promocode_toggle_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_toggle_"))(promocode_toggle)
promocode_delete_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_delete_"))(promocode_delete)

# Пользователь: получение промокода
get_promocode_handler = bot.callback_query_handler(lambda c: c.data == "get_promocode")(get_user_promocode)
promocode_select_category_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_cat_text_"))(promocode_select_category)
promocode_choose_actions_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_cat_select_"))(promocode_choose_actions)
user_select_category_handler = bot.callback_query_handler(lambda c: c.data.startswith("get_promocode_cat_"))(user_select_category)
promocode_select_category_file_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_cat_file_"))(promocode_select_category_file)
promocode_back_to_category_handler = bot.callback_query_handler(lambda c: c.data.startswith("promocode_back_to_category_"))(promocode_back_to_category)

# Новые обработчики для пользовательских промокодов
from bot.handlers.promocodes import claim_promocode, get_category_instruction
claim_promocode_handler = bot.callback_query_handler(lambda c: c.data.startswith("claim_promocode_"))(claim_promocode)
get_instruction_handler = bot.callback_query_handler(lambda c: c.data.startswith("get_instruction_"))(get_category_instruction)

# Старые обработчики поддержки (для обратной совместимости)
support_ozon_old_handler = bot.callback_query_handler(lambda c: c.data == "help_ozon")(support_ozon)
support_wildberries_old_handler = bot.callback_query_handler(lambda c: c.data == "help_wildberries")(support_wildberries)



# Обработчики для гарантийных случаев с выбором платформы
warranty_case_ozon_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_case_ozon"))(warranty_case_ozon)
warranty_case_wb_handler = bot.callback_query_handler(lambda c: c.data.startswith("warranty_case_wb"))(warranty_case_wildberries)

