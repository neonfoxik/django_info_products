# Функция handle_callback удалена - все callback'и теперь обрабатываются через views.py

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
    show_admin_panel,
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
    support_wildberries,
    warranty_case_platform_choice,
    warranty_case_ozon,
    warranty_case_wildberries
)

from .registration import start_registration
from .support import (
    show_support_menu, start_support_ozon, start_support_wildberries,
    close_support_ticket, accept_support_ticket, finish_ticket_processing,
    view_ticket_details, already_assigned_callback, admin_list_open_tickets,
    admin_start_broadcast, admin_broadcast_confirm, send_broadcast_to_all_users,
    admin_back_to_tickets, admin_list_my_tickets, support_start, support_select_category,
    support_select_product, support_select_issue, support_helped, support_not_helped, support_other
)
from .promocodes import (
    promocode_menu, promocode_add, promocode_list, promocode_detail,
    promocode_toggle, promocode_delete, get_user_promocode, 
    user_select_category, claim_promocode, get_category_instruction,
    promocode_select_category, handle_promocode_text, handle_promocode_document, 
    promocode_select_category_file, promocode_choose_actions, promocode_back_to_category, promocode_state
)
from .warranty import (
    warranty_start, warranty_select_category, warranty_select_product,
    warranty_select_issue, warranty_helped, warranty_not_helped, warranty_other
)