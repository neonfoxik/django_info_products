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
    activate_warranty,
    cancel_warranty_activation,
    show_my_warranties,
    check_screenshot,
    confirm_review,
    cancel_review,
    send_excel_to_admin,
    admin_command,
    show_warranty_cases,
    handle_warranty_case,
    send_instruction_pdf,
    send_faq_pdf,
    send_product_instruction_pdf,
    request_contact_for_warranty,
    process_warranty_case_contact,
    process_warranty_case_description,
    show_warranty_main_menu,
    show_warranty_conditions,
    show_warranty_activation_menu,
    waranty_goods_fast,
    support_main_menu,
    support_ozon,
    support_wildberries
)

from .registration import start_registration

from telebot.types import CallbackQuery
from bot import bot, logger

def handle_callback(call: CallbackQuery) -> None:
    """Обработчик callback-запросов"""
    try:
        if call.data == "menu":
            menu_call(call)
        elif call.data == "my_warranties":
            show_my_warranties(call)
        elif call.data == "warranty_main_menu":
            show_warranty_main_menu(call)
        elif call.data == "warranty_conditions":
            show_warranty_conditions(call)
        elif call.data == "warranty_activation_menu":
            show_warranty_activation_menu(call)
        elif call.data == "waranty_goods_fast":
            waranty_goods_fast(call)
        elif call.data == "warranty_cases":
            show_warranty_cases(call)
        elif call.data.startswith("warranty_case_"):
            handle_warranty_case(call)
        elif call.data.startswith("atwarranty_case_"):
            handle_warranty_case(call)
        elif call.data.startswith("request_contact_"):
            request_contact_for_warranty(call)
        elif call.data.startswith("instruction_pdf_"):
            send_instruction_pdf(call)
        elif call.data.startswith("product_instruction_pdf_"):
            send_product_instruction_pdf(call)
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
        elif call.data == "admin_excel":
            send_excel_to_admin(call)
        elif call.data == "catalog":
            show_categories(call.message.chat.id, call.message.message_id)
        elif call.data == "help_main":
            support_main_menu(call)
        elif call.data == "help_ozon":
            support_ozon(call)
        elif call.data == "help_wildberries":
            support_wildberries(call)
        elif call.data == "category_header":
            # Заголовки категорий - просто игнорируем нажатие
            bot.answer_callback_query(
                callback_query_id=call.id,
                text=""
            )
        else:
            # Если callback не обработан, отправляем сообщение об ошибке
            bot.answer_callback_query(
                callback_query_id=call.id,
                text="Неизвестная команда"
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_callback: {e}")
        bot.answer_callback_query(
            callback_query_id=call.id,
            text="Произошла ошибка. Попробуйте позже."
        )
