from telebot.types import Message, CallbackQuery
from django.utils import timezone
from bot import bot
from bot.models import User, SupportTicket, SupportMessage, OwnerSettings
from bot.texts import (
    SUPPORT_WELCOME_TEXT, SUPPORT_OZON_START_TEXT, SUPPORT_WILDBERRIES_START_TEXT,
    SUPPORT_MESSAGE_RECEIVED_TEXT, SUPPORT_TICKET_CLOSED_TEXT,
    ADMIN_NEW_TICKET_TEXT, ADMIN_TICKET_ASSIGNED_TEXT, ADMIN_TICKET_ALREADY_ASSIGNED_TEXT,
    ADMIN_RESPONSE_SENT_TEXT, ADMIN_TICKET_FINISHED_TEXT,
    ADMIN_REMINDER_TEXT, OWNER_NOTIFICATION_TEXT
)
from bot.keyboards import (
    get_support_platform_markup, get_close_ticket_markup, 
    get_admin_ticket_markup, get_admin_response_markup, main_markup,
    get_user_tickets_list_markup, get_user_ticket_actions_markup, get_admin_my_tickets_markup
)
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# Словарь для отслеживания состояния пользователей в поддержке
support_state = {}
# Словарь для отслеживания состояния админов, отвечающих на обращения
admin_response_state = {}
broadcast_state = {}


def show_support_menu(call: CallbackQuery) -> None:
    """Показывает главное меню поддержки"""
    try:
        logger.info(f"[DEBUG] show_support_menu вызвана для пользователя {call.message.chat.id}")
        print(f"[DEBUG] show_support_menu вызвана для пользователя {call.message.chat.id}")
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=SUPPORT_WELCOME_TEXT,
            reply_markup=get_support_platform_markup()
        )
        bot.answer_callback_query(call.id)
        
        logger.info(f"[DEBUG] show_support_menu выполнена успешно")
        print(f"[DEBUG] show_support_menu выполнена успешно")
    except Exception as e:
        logger.error(f"Ошибка в show_support_menu: {e}")
        print(f"[ERROR] Ошибка в show_support_menu: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def show_user_tickets(call: CallbackQuery) -> None:
    """Показывает список активных обращений пользователя"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        # Активные: open и in_progress
        tickets = list(user.support_tickets.filter(status__in=["open", "in_progress"]).order_by("-created_at"))

        if not tickets:
            bot.answer_callback_query(call.id, "Активных обращений нет")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="У вас нет активных обращений.",
                reply_markup=get_support_platform_markup()
            )
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🗂 Ваши активные обращения:",
            reply_markup=get_user_tickets_list_markup(tickets)
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в show_user_tickets: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def show_user_ticket_actions(call: CallbackQuery) -> None:
    """Показывает действия по выбранному обращению"""
    try:
        ticket_id = int(call.data.split("_")[-1])
        ticket = SupportTicket.objects.get(id=ticket_id)

        if ticket.status == "closed":
            bot.answer_callback_query(call.id, "Обращение уже закрыто")
            return

        header = (
            f"📋 Обращение #{ticket.id}\n"
            f"📱 Платформа: {ticket.get_platform_display()}\n"
            f"📊 Статус: {ticket.get_status_display()}\n\n"
            f"Выберите действие:"
        )
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=header,
            reply_markup=get_user_ticket_actions_markup(ticket.id)
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в show_user_ticket_actions: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def user_close_ticket(call: CallbackQuery) -> None:
    """Закрывает выбранное пользователем обращение (из списка)"""
    try:
        ticket_id = int(call.data.split("_")[-1])
        ticket = SupportTicket.objects.get(id=ticket_id)
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.save()

        # Убираем состояние, если было
        if ticket.user.telegram_id in support_state:
            del support_state[ticket.user.telegram_id]

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Обращение закрыто",
            reply_markup=get_support_platform_markup()
        )
        
        # Уведомить назначенного админа
        if ticket.assigned_admin:
            try:
                bot.send_message(ticket.assigned_admin.telegram_id, f"ℹ️ Пользователь закрыл обращение #{ticket.id}")
            except:
                pass

        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в user_close_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def user_open_ticket(call: CallbackQuery) -> None:
    """Открывает выбранное обращение для продолжения переписки"""
    try:
        ticket_id = int(call.data.split("_")[-1])
        ticket = SupportTicket.objects.get(id=ticket_id)

        # Включаем состояние поддержки для пользователя
        support_state[call.message.chat.id] = {
            'ticket_id': ticket.id,
            'platform': ticket.platform
        }

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "✍️ Продолжайте переписку по обращению "
                f"#{ticket.id}. Напишите ваше сообщение."
            )
        )
        # Короткое уведомление админам, что пользователь возобновил переписку
        try:
            _notify_admins_user_continues(ticket)
        except Exception as e:
            logger.error(f"Ошибка уведомления админов о продолжении тикета #{ticket.id}: {e}")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в user_open_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def admin_start_broadcast(call: CallbackQuery) -> None:
    """Запрашивает у админа текст рассылки"""
    try:
        admin = User.objects.get(telegram_id=call.message.chat.id)
        if not admin.is_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        broadcast_state[call.message.chat.id] = {"awaiting_text": True}
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📢 Введите текст рассылки одним сообщением."
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в admin_start_broadcast: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def handle_admin_broadcast_text(message: Message) -> bool:
    """Принимает текст рассылки от админа и просит подтверждение"""
    try:
        if message.chat.id not in broadcast_state or not broadcast_state[message.chat.id].get("awaiting_text"):
            return False
        broadcast_state[message.chat.id] = {"text": message.text, "confirm": True}
        from bot.keyboards import get_broadcast_confirm_markup
        bot.send_message(
            chat_id=message.chat.id,
            text=f"Предпросмотр рассылки:\n\n{message.text}\n\nОтправить всем пользователям?",
            reply_markup=get_broadcast_confirm_markup()
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_broadcast_text: {e}")
        return False


def admin_broadcast_confirm(call: CallbackQuery) -> None:
    """Подтверждение/отмена рассылки"""
    try:
        state = broadcast_state.get(call.message.chat.id)
        if not state or "text" not in state:
            bot.answer_callback_query(call.id, "Нет черновика рассылки")
            return
        if call.data == "broadcast_cancel":
            broadcast_state.pop(call.message.chat.id, None)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Рассылка отменена."
            )
            bot.answer_callback_query(call.id)
            return

        # Отправка
        text = state["text"]
        from bot.models import User as UModel
        sent = 0
        for u in UModel.objects.all():
            try:
                bot.send_message(u.telegram_id, text)
                sent += 1
            except Exception:
                continue
        broadcast_state.pop(call.message.chat.id, None)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Рассылка отправлена. Сообщений: {sent}"
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в admin_broadcast_confirm: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def send_broadcast_to_all_users(broadcast_message) -> None:
    """Отправляет рассылку всем пользователям"""
    try:
        from bot.models import BroadcastMessage
        
        # Получаем всех пользователей
        users = User.objects.filter(is_active=True)
        sent_count = 0
        failed_count = 0
        
        for user in users:
            try:
                bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"📢 {broadcast_message.message_text}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки рассылки пользователю {user.telegram_id}: {e}")
                failed_count += 1
        
        # Обновляем статус рассылки
        broadcast_message.is_sent = True
        broadcast_message.sent_at = timezone.now()
        broadcast_message.save()
        
        logger.info(f"Рассылка завершена. Отправлено: {sent_count}, ошибок: {failed_count}")
        
    except Exception as e:
        logger.error(f"Ошибка в send_broadcast_to_all_users: {e}")


def start_support_ozon(call: CallbackQuery) -> None:
    """Начинает создание обращения для Озон"""
    try:
        logger.info(f"[DEBUG] start_support_ozon вызвана для пользователя {call.message.chat.id}")
        print(f"[DEBUG] start_support_ozon вызвана для пользователя {call.message.chat.id}")
        
        user, created = User.objects.get_or_create(telegram_id=call.message.chat.id)
        
        # Проверяем, есть ли уже открытое обращение
        existing_ticket = SupportTicket.objects.filter(
            user=user, 
            status__in=['open', 'in_progress']
        ).first()
        
        if existing_ticket:
            # Переводим пользователя в контекст существующего тикета
            support_state[call.message.chat.id] = {
                'ticket_id': existing_ticket.id,
                'platform': existing_ticket.platform
            }

            # Не уведомляем админов здесь; уведомим при следующем сообщении пользователя

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"✍️ Продолжайте переписку по вашему обращению #{existing_ticket.id}.\n"
                    "Напишите ваше сообщение."
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем новое обращение
        ticket = SupportTicket.objects.create(
            user=user,
            platform='ozon',
            status='open'
        )
        
        # Уведомляем админов о новом обращении сразу после его создания
        try:
            notify_admins_about_new_ticket(ticket)
        except Exception as e:
            logger.error(f"Ошибка уведомления админов о новом тикете #{ticket.id}: {e}")
        
        # Устанавливаем состояние пользователя
        support_state[call.message.chat.id] = {
            'ticket_id': ticket.id,
            'platform': 'ozon'
        }
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=SUPPORT_OZON_START_TEXT,
            reply_markup=None
        )
        
        # Не уведомляем админов на создании, уведомим после первого сообщения пользователя
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в start_support_ozon: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def start_support_wildberries(call: CallbackQuery) -> None:
    """Начинает создание обращения для Вайлдберриз"""
    try:
        logger.info(f"[DEBUG] start_support_wildberries вызвана для пользователя {call.message.chat.id}")
        print(f"[DEBUG] start_support_wildberries вызвана для пользователя {call.message.chat.id}")
        
        user, created = User.objects.get_or_create(telegram_id=call.message.chat.id)
        
        # Проверяем, есть ли уже открытое обращение
        existing_ticket = SupportTicket.objects.filter(
            user=user, 
            status__in=['open', 'in_progress']
        ).first()
        
        if existing_ticket:
            # Переводим пользователя в контекст существующего тикета
            support_state[call.message.chat.id] = {
                'ticket_id': existing_ticket.id,
                'platform': existing_ticket.platform
            }

            # Не уведомляем админов здесь; уведомим при следующем сообщении пользователя

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"✍️ Продолжайте переписку по вашему обращению #{existing_ticket.id}.\n"
                    "Напишите ваше сообщение."
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем новое обращение
        ticket = SupportTicket.objects.create(
            user=user,
            platform='wildberries',
            status='open'
        )
        
        # Уведомляем админов о новом обращении сразу после его создания
        try:
            notify_admins_about_new_ticket(ticket)
        except Exception as e:
            logger.error(f"Ошибка уведомления админов о новом тикете #{ticket.id}: {e}")
        
        # Устанавливаем состояние пользователя
        support_state[call.message.chat.id] = {
            'ticket_id': ticket.id,
            'platform': 'wildberries'
        }
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=SUPPORT_WILDBERRIES_START_TEXT,
            reply_markup=None
        )
        
        # Не уведомляем админов на создании, уведомим после первого сообщения пользователя
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в start_support_wildberries: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def handle_support_message(message: Message) -> None:
    """Обрабатывает сообщения пользователей в поддержке"""
    try:
        chat_id = message.chat.id
        
        # Проверяем, есть ли пользователь в состоянии поддержки
        if chat_id not in support_state:
            return False
        
        user = User.objects.get(telegram_id=chat_id)
        ticket_id = support_state[chat_id]['ticket_id']
        ticket = SupportTicket.objects.get(id=ticket_id)
        
        # Проверяем, не закрыто ли уже обращение
        if ticket.status == 'closed':
            bot.send_message(
                chat_id=chat_id,
                text="❌ Обращение уже закрыто. Вы не можете отправлять сообщения в закрытое обращение."
            )
            # Удаляем состояние пользователя
            del support_state[chat_id]
            return True
        
        # Определяем тип контента и сохраняем сообщение пользователя
        content_type = 'text'
        file_id = None
        caption = None
        message_text = None

        if getattr(message, 'photo', None):
            content_type = 'photo'
            file_id = message.photo[-1].file_id
            caption = message.caption
        elif getattr(message, 'video', None):
            content_type = 'video'
            file_id = message.video.file_id
            caption = message.caption
        elif getattr(message, 'document', None):
            content_type = 'document'
            file_id = message.document.file_id
            caption = message.caption
        elif getattr(message, 'text', None):
            content_type = 'text'
            message_text = message.text

        SupportMessage.objects.create(
            ticket=ticket,
            sender=user,
            sender_type='user',
            message_text=message_text or (caption or ''),
            telegram_message_id=str(message.message_id),
            content_type=content_type,
            file_id=file_id,
            caption=caption,
        )
        # Обновляем метки тикета
        ticket.unread_by_admin = True
        ticket.last_message_at = timezone.now()
        ticket.last_message_from = 'user'
        ticket.messages_count = (ticket.messages_count or 0) + 1
        ticket.save(update_fields=['unread_by_admin','last_message_at','last_message_from','messages_count'])
        
        # Отправляем подтверждение пользователю
        try:
            bot.send_message(
                chat_id=chat_id,
                text=SUPPORT_MESSAGE_RECEIVED_TEXT
            )
        except Exception:
            pass
        
        # Пересылаем сообщение только назначенному администратору (если есть)
        try:
            if ticket.assigned_admin:
                _forward_to_admins(ticket, message)
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения назначенному админу по тикету #{ticket.id}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в handle_support_message: {e}")
        return False


def close_support_ticket(call: CallbackQuery) -> None:
    """Закрывает обращение по запросу пользователя"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Находим активное обращение пользователя
        ticket = SupportTicket.objects.filter(
            user=user,
            status__in=['open', 'in_progress']
        ).first()
        
        if not ticket:
            bot.answer_callback_query(call.id, "У вас нет активных обращений.")
            return
        
        # Проверяем, не закрыто ли уже обращение
        if ticket.status == 'closed':
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Обращение уже закрыто."
            )
            bot.answer_callback_query(call.id, "Обращение уже закрыто")
            return
        
        # Закрываем обращение
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.save()
        
        # Удаляем состояние пользователя
        if call.message.chat.id in support_state:
            del support_state[call.message.chat.id]
        
        # Уведомляем админа, если он был назначен
        if ticket.assigned_admin:
            admin_chat_id = ticket.assigned_admin.telegram_id
            if admin_chat_id in admin_response_state:
                del admin_response_state[admin_chat_id]
            
            bot.send_message(
                chat_id=admin_chat_id,
                text=f"ℹ️ Пользователь {user.user_name} закрыл обращение #{ticket.id}."
            )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=SUPPORT_TICKET_CLOSED_TEXT,
            reply_markup=main_markup
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в close_support_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def accept_support_ticket(call: CallbackQuery) -> None:
    """Админ принимает обращение"""
    try:
        # Извлекаем ID тикета из callback_data
        ticket_id = int(call.data.split('_')[-1])
        admin = User.objects.get(telegram_id=call.message.chat.id)
        
        with transaction.atomic():
            ticket = SupportTicket.objects.select_for_update().get(id=ticket_id)
            
            # Проверяем, не принято ли уже обращение
            if ticket.assigned_admin:
                bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=get_admin_ticket_markup(ticket_id, is_assigned=True)
                )
                bot.answer_callback_query(call.id, ADMIN_TICKET_ALREADY_ASSIGNED_TEXT)
                return
            
            # Назначаем админа
            ticket.assigned_admin = admin
            ticket.status = 'in_progress'
            ticket.unread_by_user = True
            ticket.unread_by_admin = False
            ticket.last_message_at = timezone.now()
            ticket.last_message_from = 'admin'
            ticket.save()
        
        # Собираем историю сообщений
        messages = SupportMessage.objects.filter(ticket=ticket).order_by('created_at')
        message_history = ""
        for msg in messages:
            timestamp = msg.created_at.strftime('%H:%M %d.%m.%Y')
            message_history += f"[{timestamp}] {msg.sender.user_name}: {msg.message_text}\n\n"
        
        if not message_history:
            message_history = "Пока нет сообщений от пользователя."
        
        # Устанавливаем состояние админа
        admin_response_state[call.message.chat.id] = {
            'ticket_id': ticket_id
        }
        
        # Отправляем админу информацию об обращении (с заменой сообщения)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Вы приняли обращение #{ticket_id}\n\n" + ADMIN_TICKET_ASSIGNED_TEXT.format(
                ticket_id=ticket_id,
                message_history=message_history
            ),
            reply_markup=get_admin_response_markup(ticket_id)
        )
        
        # Уведомляем пользователя, что обращение принято
        try:
            bot.send_message(
                chat_id=ticket.user.telegram_id,
                text=f"✅ Ваше обращение #{ticket_id} принято администратором {admin.user_name}.\n\n"
                     f"Администратор ответит в ближайшее время."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {ticket.user.telegram_id}: {e}")
        
        # Уведомляем других админов, что обращение принято
        admins = User.objects.filter(is_admin=True).exclude(telegram_id=admin.telegram_id)
        for other_admin in admins:
            try:
                bot.send_message(
                    chat_id=other_admin.telegram_id,
                    text=f"ℹ️ Обращение #{ticket_id} принято администратором {admin.user_name}."
                )
            except:
                pass
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в accept_support_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def handle_admin_response(message: Message) -> None:
    """Обрабатывает ответы админов на обращения"""
    try:
        chat_id = message.chat.id
        
        # Проверяем, есть ли админ в состоянии ответа
        if chat_id not in admin_response_state:
            return False
        
        admin = User.objects.get(telegram_id=chat_id)
        ticket_id = admin_response_state[chat_id]['ticket_id']
        ticket = SupportTicket.objects.get(id=ticket_id)
        
        # Проверяем, не закрыто ли уже обращение
        if ticket.status == 'closed':
            bot.send_message(
                chat_id=chat_id,
                text="❌ Обращение уже закрыто пользователем. Вы не можете отправлять сообщения в закрытое обращение."
            )
            # Удаляем состояние админа
            del admin_response_state[chat_id]
            return True
        
        # Сохраняем ответ админа
        SupportMessage.objects.create(
            ticket=ticket,
            sender=admin,
            sender_type='admin',
            message_text=message.text,
            telegram_message_id=str(message.message_id)
        )
        
        # Отправляем ответ пользователю
        bot.send_message(
            chat_id=ticket.user.telegram_id,
            text=f"💬 Ответ от поддержки:\n\n{message.text}",
            reply_markup=get_close_ticket_markup()
        )
        
        # Подтверждаем админу
        bot.send_message(
            chat_id=chat_id,
            text=ADMIN_RESPONSE_SENT_TEXT,
            reply_markup=get_admin_response_markup(ticket_id)
        )
        # Обновляем тикет: прочитано админом, непрочитано пользователем
        ticket.unread_by_user = True
        ticket.unread_by_admin = False
        ticket.last_message_at = timezone.now()
        ticket.last_message_from = 'admin'
        ticket.messages_count = (ticket.messages_count or 0) + 1
        ticket.save(update_fields=['unread_by_user','unread_by_admin','last_message_at','last_message_from','messages_count'])
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_response: {e}")
        return False


def finish_ticket_processing(call: CallbackQuery) -> None:
    """Админ завершает обработку обращения"""
    try:
        ticket_id = int(call.data.split('_')[-1])
        admin = User.objects.get(telegram_id=call.message.chat.id)
        
        # Получаем тикет и проверяем его статус
        ticket = SupportTicket.objects.get(id=ticket_id)
        
        # Если обращение уже закрыто, уведомляем админа
        if ticket.status == 'closed':
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ Обращение уже закрыто пользователем."
            )
            bot.answer_callback_query(call.id, "Обращение уже закрыто")
            return
        
        # Закрываем обращение
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.save()
        
        # Удаляем состояние админа
        if call.message.chat.id in admin_response_state:
            del admin_response_state[call.message.chat.id]
        
        # Уведомляем пользователя о завершении обращения
        try:
            bot.send_message(
                chat_id=ticket.user.telegram_id,
                text=f"✅ Ваше обращение #{ticket_id} завершено администратором {admin.user_name}.\n\n"
                     f"Если у вас остались вопросы, вы можете создать новое обращение в разделе 'Поддержка'."
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {ticket.user.telegram_id}: {e}")
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=ADMIN_TICKET_FINISHED_TEXT
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в finish_ticket_processing: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def view_ticket_details(call: CallbackQuery) -> None:
    """Показывает детали обращения админу"""
    try:
        ticket_id = int(call.data.split('_')[-1])
        ticket = SupportTicket.objects.get(id=ticket_id)
        
        # Собираем полную историю сообщений
        messages = SupportMessage.objects.filter(ticket=ticket).order_by('created_at')
        message_history = f"📋 Обращение #{ticket_id}\n"
        message_history += f"👤 Пользователь: {ticket.user.user_name}\n"
        message_history += f"📱 Платформа: {ticket.get_platform_display()}\n"
        message_history += f"📅 Создано: {ticket.created_at.strftime('%H:%M %d.%m.%Y')}\n"
        message_history += f"📊 Статус: {ticket.get_status_display()}\n\n"
        
        if ticket.assigned_admin:
            message_history += f"👨‍💼 Назначенный админ: {ticket.assigned_admin.user_name}\n\n"
        
        message_history += "💬 История сообщений:\n"
        
        for msg in messages:
            timestamp = msg.created_at.strftime('%H:%M %d.%m.%Y')
            sender_type = "👤" if msg.sender_type == 'user' else "👨‍💼"
            message_history += f"{sender_type} [{timestamp}] {msg.sender.user_name}:\n{msg.message_text}\n\n"
        
        if not messages:
            message_history += "Пока нет сообщений.\n"
        
        # Обрезаем сообщение, если оно слишком длинное
        if len(message_history) > 4000:
            message_history = message_history[:3900] + "\n\n... (сообщение обрезано)"
        
        # Помечаем как прочитанное админом
        ticket.unread_by_admin = False
        ticket.save(update_fields=['unread_by_admin'])

        # Заменяем исходное сообщение и предлагаем принять/отказаться
        from bot.keyboards import get_admin_ticket_decision_markup
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=message_history,
            reply_markup=get_admin_ticket_decision_markup(ticket_id)
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в view_ticket_details: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def admin_list_open_tickets(call: CallbackQuery) -> None:
    """Показывает админу все открытые обращения без назначенного администратора"""
    try:
        from bot.keyboards import get_admin_open_tickets_markup
        tickets = SupportTicket.objects.filter(status__in=["open", "in_progress"], assigned_admin__isnull=True).order_by("-created_at")
        if not tickets.exists():
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Нет активных свободных обращений.")
            bot.answer_callback_query(call.id)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📬 Активные обращения (свободные):",
            reply_markup=get_admin_open_tickets_markup(list(tickets))
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в admin_list_open_tickets: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def admin_list_my_tickets(call: CallbackQuery) -> None:
    """Показывает обращения, назначенные на текущего админа"""
    try:
        admin = User.objects.get(telegram_id=call.message.chat.id)
        tickets = SupportTicket.objects.filter(assigned_admin=admin, status__in=["open","in_progress"]).order_by('-last_message_at','-created_at')
        from bot.keyboards import get_admin_my_tickets_markup
        if not tickets.exists():
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="У вас нет активных обращений.",
                reply_markup=get_admin_my_tickets_markup([])
            )
            bot.answer_callback_query(call.id)
            return
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Мои обращения:",
            reply_markup=get_admin_my_tickets_markup(list(tickets))
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в admin_list_my_tickets: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def decline_support_ticket(call: CallbackQuery) -> None:
    """Админ отказывается от обращения (ничего не меняем в тикете)"""
    try:
        ticket_id = int(call.data.split('_')[-1])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"❌ Вы отказались от обращения #{ticket_id}.")
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в decline_support_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def notify_admins_about_new_ticket(ticket: SupportTicket) -> None:
    """Уведомляет всех админов о новом обращении"""
    try:
        admins = User.objects.filter(is_admin=True)
        for admin in admins:
            try:
                bot.send_message(
                    chat_id=admin.telegram_id,
                    text=ADMIN_NEW_TICKET_TEXT.format(
                        user_name=ticket.user.user_name,
                        platform=ticket.get_platform_display(),
                        created_at=ticket.created_at.strftime('%H:%M %d.%m.%Y')
                    ),
                    reply_markup=get_admin_ticket_markup(ticket.id)
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления админу {admin.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в notify_admins_about_new_ticket: {e}")


def already_assigned_callback(call: CallbackQuery) -> None:
    """Обрабатывает нажатие на кнопку 'уже принято'"""
    bot.answer_callback_query(call.id, ADMIN_TICKET_ALREADY_ASSIGNED_TEXT)


def _forward_to_admins(ticket: SupportTicket, message: Message) -> None:
    """Пересылает сообщение пользователя админам с нужными кнопками."""
    admins = []
    if ticket.assigned_admin:
        admins = [ticket.assigned_admin]
    else:
        admins = list(User.objects.filter(is_admin=True))

    for admin in admins:
        try:
            header = f"Новое сообщение по обращению #{ticket.id} от {ticket.user.user_name}"
            if getattr(message, 'photo', None):
                bot.send_photo(admin.telegram_id, message.photo[-1].file_id, caption=(message.caption or header), reply_markup=get_admin_ticket_markup(ticket.id))
            elif getattr(message, 'video', None):
                bot.send_video(admin.telegram_id, message.video.file_id, caption=(message.caption or header), reply_markup=get_admin_ticket_markup(ticket.id))
            elif getattr(message, 'document', None):
                bot.send_document(admin.telegram_id, message.document.file_id, caption=(message.caption or header), reply_markup=get_admin_ticket_markup(ticket.id))
            elif getattr(message, 'text', None):
                bot.send_message(admin.telegram_id, f"{header}\n\n{message.text}", reply_markup=get_admin_ticket_markup(ticket.id))
            else:
                bot.send_message(admin.telegram_id, header, reply_markup=get_admin_ticket_markup(ticket.id))
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin.telegram_id}: {e}")


def _notify_admins_user_continues(ticket: SupportTicket) -> None:
    """Уведомляет ТОЛЬКО назначенного админа при возобновлении переписки пользователем.
    Если админ не назначен — не уведомляем никого (во избежание спама)."""
    if not ticket.assigned_admin:
        return
    text = f"Пользователь {ticket.user.user_name} продолжает переписку по обращению #{ticket.id}"
    try:
        bot.send_message(ticket.assigned_admin.telegram_id, text, reply_markup=get_admin_ticket_markup(ticket.id))
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления назначенному админу {ticket.assigned_admin.telegram_id}: {e}")
