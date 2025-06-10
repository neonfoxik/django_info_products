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
    show_warranty_handler,
    show_warranty_cases,
    handle_warranty_case
)

from .registration import start_registration

from telebot.types import CallbackQuery

def handle_callback(call: CallbackQuery) -> None:
    """Обработчик callback-запросов"""
    if call.data == "menu":
        menu_call(call)
    elif call.data == "warranty_case":
        show_warranty_handler(call)
    elif call.data == "warranty_cases":
        show_warranty_cases(call)
    elif call.data.startswith("warranty_case_"):
        handle_warranty_case(call)
    # ... остальные обработчики ...
