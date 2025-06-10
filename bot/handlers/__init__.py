from .common import (
    start, 
    menu_call, 
    menu_m, 
    show_categories,
    show_category_products, 
    show_product_menu, 
    show_product_info, 
    chat_with_ai,
    back_to_main,
    back_to_categories,
    support_menu,
    activate_warranty,
    cancel_warranty_activation,
    show_my_warranties,
    check_screenshot,
    confirm_review,
    cancel_review,
    send_excel_to_admin,
    admin_command,
    show_warranty_cases,
    handle_warranty_case
)

from .registration import start_registration

from telebot.types import CallbackQuery
from bot import bot, logger

def handle_callback(call: CallbackQuery) -> None:
    """Обработчик callback-запросов"""
    try:
        if call.data == "menu":
            menu_call(call)
        elif call.data == "warranty_cases":
            show_warranty_cases(call)
        elif call.data.startswith("warranty_case_"):
            handle_warranty_case(call)
        elif call.data.startswith("instructions_") or call.data.startswith("faq_") or call.data.startswith("warranty_"):
            show_product_info(call)
        elif call.data.startswith("category_"):
            show_category_products(call)
        elif call.data.startswith("product_"):
            show_product_menu(call)
        elif call.data.startswith("activate_warranty_"):
            activate_warranty(call)
        elif call.data.startswith("cancel_warranty_"):
            cancel_warranty_activation(call)
        elif call.data.startswith("confirm_review_"):
            confirm_review(call)
        elif call.data.startswith("cancel_review_"):
            cancel_review(call)
        elif call.data == "back_to_main":
            back_to_main(call)
        elif call.data == "back_to_categories":
            back_to_categories(call)
        elif call.data == "support_menu":
            support_menu(call)
        elif call.data == "show_my_warranties":
            show_my_warranties(call)
        elif call.data == "send_excel":
            send_excel_to_admin(call)
        else:
            print(f"[WARNING] Неизвестный callback_data: {call.data}")
            logger.warning(f"[WARNING] Неизвестный callback_data: {call.data}")
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке callback: {e}")
        logger.error(f"[ERROR] Ошибка при обработке callback: {e}")
        # Отправляем сообщение пользователю об ошибке
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Пожалуйста, попробуйте снова."
        )
