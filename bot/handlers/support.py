from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from django.utils import timezone
from bot import bot
from bot.models import User, SupportTicket, SupportMessage, OwnerSettings, WarrantyRequest, WarrantyAnswer, goods, goods_category, TypicalIssue, ProductSupportQuestion, ProductWarrantyQuestion, SupportAnswer
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
    get_user_tickets_list_markup, get_user_ticket_actions_markup, get_admin_my_tickets_markup, get_ticket_files_markup
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
# Контекст для переноса деталей из гарантийного обращения в новое обращение поддержки
warranty_to_support_context = {}
# Словарь для отслеживания анкеты поддержки
support_qna_state = {}
# Контекст для переноса деталей из обращения в поддержку в новое обращение поддержки
support_to_support_context = {}

# ===== Helpers for tracking and cleanup admin chat messages =====
def _track_admin_message(ticket: SupportTicket, admin_chat_id: int, message_id: int) -> None:
    try:
        key = str(admin_chat_id)
        ticket.admin_messages = ticket.admin_messages or {}
        ticket.admin_messages.setdefault(key, [])
        ticket.admin_messages[key].append(int(message_id))
        ticket.save(update_fields=['admin_messages'])
    except Exception:
        # Не мешаем основному потоку при ошибке учета
        pass


def _cleanup_admin_messages(ticket: SupportTicket) -> None:
    try:
        mapping = ticket.admin_messages or {}
        for admin_chat_id_str, ids in mapping.items():
            try:
                admin_chat_id = int(admin_chat_id_str)
            except Exception:
                continue
            for mid in ids or []:
                try:
                    bot.delete_message(admin_chat_id, int(mid))
                except Exception:
                    # Сообщение могло быть уже удалено или недоступно — игнорируем
                    continue
        # Сбрасываем учет после очистки
        ticket.admin_messages = {}
        ticket.save(update_fields=['admin_messages'])
    except Exception:
        pass


# ===== Helpers for admin roles and permissions =====
def is_any_admin(u: User) -> bool:
    return bool(getattr(u, 'is_super_admin', False) or getattr(u, 'is_ozon_admin', False) or getattr(u, 'is_wb_admin', False) or getattr(u, 'is_admin', False))


def is_super_admin(u: User) -> bool:
    return bool(getattr(u, 'is_super_admin', False))


def admin_can_handle_ticket(u: User, t: SupportTicket) -> bool:
    if is_super_admin(u) or getattr(u, 'is_admin', False):
        return True
    if t.platform == 'ozon' and getattr(u, 'is_ozon_admin', False):
        return True
    if t.platform == 'wildberries' and getattr(u, 'is_wb_admin', False):
        return True
    return False


def get_relevant_admins_for_ticket(t: SupportTicket):
    qs = User.objects.none()
    base_all = User.objects.filter(is_admin=True)
    super_admins = User.objects.filter(is_super_admin=True)
    if t.platform == 'ozon':
        platform_admins = User.objects.filter(is_ozon_admin=True)
    else:
        platform_admins = User.objects.filter(is_wb_admin=True)
    return (base_all | super_admins | platform_admins).distinct()


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
                sent = bot.send_message(ticket.assigned_admin.telegram_id, f"ℹ️ Пользователь закрыл обращение #{ticket.id}")
                _track_admin_message(ticket, ticket.assigned_admin.telegram_id, sent.message_id)
            except:
                pass

        # Чистим сообщения в чатах администраторов по этому тикету
        try:
            _cleanup_admin_messages(ticket)
        except Exception:
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
        
        # Очищаем старое состояние пользователя, если оно есть
        if call.message.chat.id in support_state:
            del support_state[call.message.chat.id]
        
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

            # Сообщаем, что новое обращение создать нельзя, пока активное не закрыто
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"ℹ️ У вас уже есть активное обращение #{existing_ticket.id}.\n\n"
                    "Вы не можете создать новое, пока текущее не будет закрыто.\n\n"
                    "✍️ Продолжайте переписку: напишите ваше сообщение."
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
        
        # Создаем ответы на вопросы поддержки, если они есть
        try:
            ctx = warranty_to_support_context.get(call.message.chat.id, None)
            if not ctx:
                ctx = support_to_support_context.get(call.message.chat.id, None)
            
            if ctx and ctx.get('answers'):
                for question_text, answer_text in ctx['answers']:
                    # Находим вопрос по тексту
                    try:
                        question = ProductSupportQuestion.objects.get(product=support_request['product'], text=question_text, is_active=True)
                        SupportAnswer.objects.create(
                            ticket=ticket,
                            question=question,
                            answer_text=answer_text
                        )
                    except ProductSupportQuestion.DoesNotExist:
                        logger.warning(f"Вопрос поддержки не найден: {question_text}")
        except Exception as e:
            logger.error(f"Ошибка создания ответов на вопросы поддержки: {e}")
        
        
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

        # Если есть контекст из гарантии или поддержки — добавляем стартовое сообщение с деталями
        try:
            ctx = warranty_to_support_context.pop(call.message.chat.id, None)
            if not ctx:
                ctx = support_to_support_context.pop(call.message.chat.id, None)
            
            if ctx and ctx.get('text'):
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    sender_type='user',
                    message_text=ctx['text'],
                    telegram_message_id=None,
                )
                ticket.unread_by_admin = True
                ticket.last_message_at = timezone.now()
                ticket.last_message_from = 'user'
                ticket.messages_count = (ticket.messages_count or 0) + 1
                ticket.save(update_fields=['unread_by_admin','last_message_at','last_message_from','messages_count'])
        except Exception:
            pass
        
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
        
        # Очищаем старое состояние пользователя, если оно есть
        if call.message.chat.id in support_state:
            del support_state[call.message.chat.id]
        
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

            # Сообщаем, что новое обращение создать нельзя, пока активное не закрыто
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    f"ℹ️ У вас уже есть активное обращение #{existing_ticket.id}.\n\n"
                    "Вы не можете создать новое, пока текущее не будет закрыто.\n\n"
                    "✍️ Продолжайте переписку: напишите ваше сообщение."
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
        
        # Создаем ответы на вопросы поддержки, если они есть
        try:
            ctx = warranty_to_support_context.get(call.message.chat.id, None)
            if not ctx:
                ctx = support_to_support_context.get(call.message.chat.id, None)
            
            if ctx and ctx.get('answers'):
                for question_text, answer_text in ctx['answers']:
                    # Находим вопрос по тексту
                    try:
                        question = ProductSupportQuestion.objects.get(product=support_request['product'], text=question_text, is_active=True)
                        SupportAnswer.objects.create(
                            ticket=ticket,
                            question=question,
                            answer_text=answer_text
                        )
                    except ProductSupportQuestion.DoesNotExist:
                        logger.warning(f"Вопрос поддержки не найден: {question_text}")
        except Exception as e:
            logger.error(f"Ошибка создания ответов на вопросы поддержки: {e}")
        
        
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

        # Если есть контекст из гарантии или поддержки — добавляем стартовое сообщение с деталями
        try:
            ctx = warranty_to_support_context.pop(call.message.chat.id, None)
            if not ctx:
                ctx = support_to_support_context.pop(call.message.chat.id, None)
            
            if ctx and ctx.get('text'):
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    sender_type='user',
                    message_text=ctx['text'],
                    telegram_message_id=None,
                )
                ticket.unread_by_admin = True
                ticket.last_message_at = timezone.now()
                ticket.last_message_from = 'user'
                ticket.messages_count = (ticket.messages_count or 0) + 1
                ticket.save(update_fields=['unread_by_admin','last_message_at','last_message_from','messages_count'])
        except Exception:
            pass
        
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
        
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
        except SupportTicket.DoesNotExist:
            # Если обращение не найдено, очищаем состояние
            if chat_id in support_state:
                del support_state[chat_id]
            return False
        
        # Проверяем, не закрыто ли уже обращение
        if ticket.status == 'closed':
            # Удаляем состояние пользователя
            if chat_id in support_state:
                del support_state[chat_id]
            # Возвращаем False, чтобы сообщение обрабатывалось дальше
            return False
        
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
        
        # Пересылка: только назначенному админу; если медиа — шлем уведомление с кнопкой получения файлов
        try:
            if ticket.assigned_admin:
                if content_type == 'text':
                    _forward_to_admins(ticket, message)
                else:
                    from bot.keyboards import get_ticket_files_markup
                    info = (
                        f"Новое вложение в обращении #{ticket.id} от {ticket.user.user_name}.\n"
                        f"Тип: {content_type}. Нажмите, чтобы получить все файлы по обращению."
                    )
                    sent = bot.send_message(ticket.assigned_admin.telegram_id, info, reply_markup=get_ticket_files_markup(ticket.id))
                    try:
                        _track_admin_message(ticket, ticket.assigned_admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Ошибка уведомления о медиа по тикету #{ticket.id}: {e}")
        
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
            
            # Проверяем право принимать по платформе (кроме супер/общих админов)
            if not admin_can_handle_ticket(admin, ticket):
                bot.answer_callback_query(call.id, "Нет доступа к этой платформе")
                return

            # Назначаем админа
            ticket.assigned_admin = admin
            ticket.status = 'in_progress'
            ticket.unread_by_user = True
            ticket.unread_by_admin = False
            ticket.last_message_at = timezone.now()
            ticket.last_message_from = 'admin'
            ticket.save()
        
        # Собираем историю сообщений (от новых к старым, чтобы влезли последние)
        messages_query = SupportMessage.objects.filter(ticket=ticket).order_by('-created_at')
        history_parts = []
        current_len = 0
        limit = 3000
        truncated = False
        
        for msg in messages_query:
            timestamp = msg.created_at.strftime('%H:%M %d.%m.%Y')
            sender_type = "👤" if msg.sender_type == 'user' else "👨‍💼"
            text = msg.message_text or (f"[{msg.content_type}]" if msg.content_type != 'text' else "")
            entry = f"{sender_type} [{timestamp}] {msg.sender.user_name}:\n{text}\n\n"
            
            if current_len + len(entry) > limit:
                truncated = True
                break
            history_parts.append(entry)
            current_len += len(entry)
        
        # Разворачиваем обратно в хронологический порядок
        history_parts.reverse()
        message_history = "".join(history_parts)
        
        if truncated:
            message_history = "⚠️ ... (старая переписка скрыта)\n\n" + message_history
            
        if not message_history and not messages_query.exists():
            message_history = "Пока нет сообщений от пользователя."

        
        # Проверяем, есть ли файлы в обращении
        has_files = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').exists()
        
        # Устанавливаем состояние админа
        admin_response_state[call.message.chat.id] = {
            'ticket_id': ticket_id
        }
        
        # Создаем клавиатуру с кнопкой получения файлов, если они есть
        from bot.keyboards import get_admin_response_markup, get_admin_response_with_files_markup
        if has_files:
            markup = get_admin_response_with_files_markup(ticket_id)
        else:
            markup = get_admin_response_markup(ticket_id)
        
        # Экранируем фигурные скобки, чтобы .format() не упал на сообщениях пользователя
        safe_history = message_history.replace('{', '{{').replace('}', '}}')
        
        # Формируем текст ответа
        response_text = ADMIN_TICKET_ASSIGNED_TEXT.format(
            ticket_id=ticket_id,
            message_history=safe_history
        )
        
        # Отправляем админу информацию об обращении (с заменой сообщения)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response_text,
            reply_markup=markup
        )


        # Учитываем сообщение-карточку, отредактированное ботом
        _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
        
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
        admins = get_relevant_admins_for_ticket(ticket).exclude(telegram_id=admin.telegram_id)
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
        
        # Определяем тип контента ответа админа
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

        # Сохраняем ответ админа
        SupportMessage.objects.create(
            ticket=ticket,
            sender=admin,
            sender_type='admin',
            message_text=message_text or (caption or ''),
            telegram_message_id=str(message.message_id),
            content_type=content_type,
            file_id=file_id,
            caption=caption,
        )

        # Отправляем ответ пользователю: медиа отправляем как медиа без дополнительных кнопок
        try:
            prefix = f"💬 Ответ от поддержки по обращению #{ticket.id}"
            if content_type == 'photo' and file_id:
                bot.send_photo(ticket.user.telegram_id, file_id, caption=(caption or prefix))
            elif content_type == 'video' and file_id:
                bot.send_video(ticket.user.telegram_id, file_id, caption=(caption or prefix))
            elif content_type == 'document' and file_id:
                bot.send_document(ticket.user.telegram_id, file_id, caption=(caption or prefix))
            else:
                # текст по-прежнему с кнопкой закрытия обращения
                bot.send_message(
                    chat_id=ticket.user.telegram_id,
                    text=f"{prefix}:\n\n{message_text}",
                    reply_markup=get_close_ticket_markup()
                )
        except Exception as e:
            logger.error(f"Ошибка отправки ответа пользователю {ticket.user.telegram_id}: {e}")

        # Эхо у админа
        try:
            if content_type == 'text':
                bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Ответ отправлен пользователю.\n\nВы: {message_text}",
                    reply_markup=get_admin_response_markup(ticket_id)
                )
            else:
                bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Медиа отправлено пользователю (тип: {content_type}).",
                    reply_markup=get_admin_response_markup(ticket_id)
                )
        except Exception:
            pass
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
            try:
                _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "Обращение уже закрыто")
            return
        
        # Закрываем обращение
        ticket.status = 'closed'
        ticket.closed_at = timezone.now()
        ticket.save()
        
        # Удаляем состояние админа
        if call.message.chat.id in admin_response_state:
            del admin_response_state[call.message.chat.id]
        
        # Удаляем состояние пользователя
        if ticket.user.telegram_id in support_state:
            del support_state[ticket.user.telegram_id]
        
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
        try:
            _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        # Чистим все сообщения, связанные с тикетом, у администраторов
        try:
            _cleanup_admin_messages(ticket)
        except Exception:
            pass
        try:
            _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        
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
        
        # Добавляем ответы на вопросы поддержки
        support_answers = SupportAnswer.objects.filter(ticket=ticket).select_related('question').order_by('created_at')
        if support_answers.exists():
            message_history += "📝 Ответы на вопросы поддержки:\n"
            for answer in support_answers:
                message_history += f"❓ {answer.question.text}\n"
                message_history += f"💬 Ответ: {answer.answer_text}\n\n"
        
        
        # Собираем историю сообщений (от новых к старым)
        messages_query = SupportMessage.objects.filter(ticket=ticket).order_by('-created_at')
        history_parts = []
        current_len = len(message_history) + 50 # Запас на заголовок "История сообщений"
        limit = 3800
        truncated = False
        
        for msg in messages_query:
            timestamp = msg.created_at.strftime('%H:%M %d.%m.%Y')
            sender_type = "👤" if msg.sender_type == 'user' else "👨‍💼"
            text = msg.message_text or (f"[{msg.content_type}]" if msg.content_type != 'text' else "")
            entry = f"{sender_type} [{timestamp}] {msg.sender.user_name}:\n{text}\n\n"
            
            if current_len + len(entry) > limit:
                truncated = True
                break
            history_parts.append(entry)
            current_len += len(entry)
            
        history_parts.reverse()
        message_history += "💬 История сообщений:\n"
        
        if truncated:
            message_history += "⚠️ ... (старая переписка скрыта)\n\n"
            
        message_history += "".join(history_parts)
        
        if not history_parts and not messages_query.exists():
            message_history += "Пока нет сообщений.\n"

        
        # Помечаем как прочитанное админом
        ticket.unread_by_admin = False
        ticket.save(update_fields=['unread_by_admin'])

        # Проверяем, назначен ли текущий админ на это обращение
        admin = User.objects.get(telegram_id=call.message.chat.id)
        
        if ticket.assigned_admin and ticket.assigned_admin.telegram_id == admin.telegram_id:
            # Если админ уже назначен на это обращение, устанавливаем состояние для ответов
            admin_response_state[call.message.chat.id] = {
                'ticket_id': ticket_id
            }
            
            # Проверяем, есть ли файлы в обращении
            has_files = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').exists()
            
            # Создаем клавиатуру для ответов
            from bot.keyboards import get_admin_response_markup, get_admin_response_with_files_markup
            if has_files:
                markup = get_admin_response_with_files_markup(ticket_id)
            else:
                markup = get_admin_response_markup(ticket_id)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=message_history + "\n\n✅ Вы назначены на это обращение. Можете отвечать пользователю.",
                reply_markup=markup
            )
            try:
                _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        else:
            # Создаем клавиатуру с кнопками действий
            markup = InlineKeyboardMarkup()
            
            # Кнопка перехвата обращения
            markup.add(InlineKeyboardButton(
                "🔄 Перехватить обращение",
                callback_data=f"takeover_ticket_{ticket_id}"
            ))
            
            # Кнопка получения файлов
            has_files = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').exists()
            if has_files:
                markup.add(InlineKeyboardButton(
                    "📎 Получить все файлы",
                    callback_data=f"get_all_ticket_files_{ticket_id}"
                ))
            
            # Кнопка назад к списку обращений
            markup.add(InlineKeyboardButton(
                "⬅️ К списку обращений",
                callback_data="admin_back_to_tickets"
            ))
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=message_history,
                reply_markup=markup
            )
            try:
                _track_admin_message(ticket, call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в view_ticket_details: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def admin_list_open_tickets(call: CallbackQuery) -> None:
    """Показывает админу все открытые обращения без назначенного администратора"""
    try:
        from bot.keyboards import get_admin_open_tickets_markup
        # Свободные тикеты: показываем релевантным админам по платформе, супер-админ видит все
        admin = User.objects.get(telegram_id=call.message.chat.id)
        base_qs = SupportTicket.objects.filter(status__in=["open", "in_progress"], assigned_admin__isnull=True)
        if is_super_admin(admin) or getattr(admin, 'is_admin', False):
            tickets = base_qs.order_by("-created_at")
        else:
            tickets = base_qs.filter(
                platform__in=(['ozon'] if getattr(admin, 'is_ozon_admin', False) else []) +
                              (['wildberries'] if getattr(admin, 'is_wb_admin', False) else [])
            ).order_by("-created_at")
        if not tickets.exists():
            from bot.keyboards import get_admin_open_tickets_markup
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Нет активных свободных обращений.",
                reply_markup=get_admin_open_tickets_markup([])
            )
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


def admin_list_in_progress_tickets(call: CallbackQuery) -> None:
    """Показывает админу все обращения в обработке (можно перехватить)"""
    try:
        from bot.keyboards import get_admin_in_progress_tickets_markup
        # В обработке: супер/общие админы видят все; платформенные видят только свою платформу
        admin = User.objects.get(telegram_id=call.message.chat.id)
        base_qs = SupportTicket.objects.filter(status="in_progress")
        if is_super_admin(admin) or getattr(admin, 'is_admin', False):
            tickets = base_qs.order_by("-updated_at")
        else:
            tickets = base_qs.filter(
                platform__in=(['ozon'] if getattr(admin, 'is_ozon_admin', False) else []) +
                              (['wildberries'] if getattr(admin, 'is_wb_admin', False) else [])
            ).order_by("-updated_at")
        if not tickets.exists():
            from bot.keyboards import get_admin_in_progress_tickets_markup
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Нет обращений в обработке.",
                reply_markup=get_admin_in_progress_tickets_markup([])
            )
            bot.answer_callback_query(call.id)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🟡 Обращения в обработке:",
            reply_markup=get_admin_in_progress_tickets_markup(list(tickets))
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в admin_list_in_progress_tickets: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def takeover_support_ticket(call: CallbackQuery) -> None:
    """Перехват обращения другим админом"""
    try:
        bot.answer_callback_query(call.id)
        ticket_id = int(call.data.split('_')[-1])
        admin = User.objects.get(telegram_id=call.message.chat.id)
        with transaction.atomic():
            ticket = SupportTicket.objects.select_for_update().get(id=ticket_id)

            # Проверяем право перехватывать по платформе (кроме супер/общих админов)
            if not admin_can_handle_ticket(admin, ticket):
                bot.answer_callback_query(call.id, "Нет доступа к этой платформе")
                return

            # Назначаем текущего админа
            ticket.assigned_admin = admin
            ticket.status = 'in_progress'
            ticket.unread_by_user = True
            ticket.unread_by_admin = False
            ticket.last_message_at = timezone.now()
            ticket.last_message_from = 'admin'
            ticket.save()

        # Устанавливаем состояние админа для ответов
        admin_response_state[call.message.chat.id] = {
            'ticket_id': ticket_id
        }
        
        # Собираем историю сообщений (от новых к старым)
        messages_query = SupportMessage.objects.filter(ticket=ticket).order_by('-created_at')
        history_parts = []
        current_len = 0
        limit = 3000
        truncated = False
        
        for msg in messages_query:
            timestamp = msg.created_at.strftime('%H:%M %d.%m.%Y')
            sender_type = "👤" if msg.sender_type == 'user' else "👨‍💼"
            text = msg.message_text or (f"[{msg.content_type}]" if msg.content_type != 'text' else "")
            entry = f"{sender_type} [{timestamp}] {msg.sender.user_name}:\n{text}\n\n"
            
            if current_len + len(entry) > limit:
                truncated = True
                break
            history_parts.append(entry)
            current_len += len(entry)
        
        history_parts.reverse()
        message_history = "".join(history_parts)
        
        if truncated:
            message_history = "⚠️ ... (старая переписка скрыта)\n\n" + message_history
            
        if not message_history and not messages_query.exists():
            message_history = "Пока нет сообщений от пользователя."

        
        # Проверяем, есть ли файлы в обращении
        has_files = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').exists()
        
        # Создаем клавиатуру с кнопкой получения файлов, если они есть
        from bot.keyboards import get_admin_response_markup, get_admin_response_with_files_markup
        if has_files:
            markup = get_admin_response_with_files_markup(ticket_id)
        else:
            markup = get_admin_response_markup(ticket_id)

        # Экранируем фигурные скобки
        safe_history = message_history.replace('{', '{{').replace('}', '}}')
        
        # Формируем текст (используем ADMIN_TICKET_ASSIGNED_TEXT, заменяя первую строку для ясности что это перехват)
        assigned_text = ADMIN_TICKET_ASSIGNED_TEXT.format(
            ticket_id=ticket_id,
            message_history=safe_history
        )
        # Заменяем "Вы приняли" на "Вы перехватили" в первой строке
        intercept_text = assigned_text.replace("Вы приняли обращение", "Вы перехватили обращение")
        
        # Сообщаем админу
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=intercept_text,
            reply_markup=markup
        )

        _track_admin_message(ticket, call.message.chat.id, call.message.message_id)

        # Уведомляем пользователя о смене администратора
        try:
            bot.send_message(
                chat_id=ticket.user.telegram_id,
                text=f"ℹ️ Ваше обращение #{ticket_id} теперь обрабатывает администратор {admin.user_name}."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя о перехвате #{ticket_id}: {e}")

        # Уведомляем предыдущего администратора, если был
        # (отправку другим админам отключить по просьбе клиента)
        # try:
        #     previous_admins = get_relevant_admins_for_ticket(ticket).exclude(telegram_id=admin.telegram_id)
        #     for other_admin in previous_admins:
        #         try:
        #             bot.send_message(other_admin.telegram_id, f"♻️ Обращение #{ticket_id} было перехвачено администратором {admin.user_name}.")
        #         except Exception:
        #             pass
        # except Exception:
        #     pass

        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в takeover_support_ticket: {e}")
        try:
            bot.answer_callback_query(call.id, "Произошла ошибка при перехвате.")
        except:
            pass



def send_ticket_files_to_admin(call: CallbackQuery) -> None:
    """Отправляет админу все нетекстовые файлы из тикета по file_id"""
    try:
        ticket_id = int(call.data.split('_')[-1])
        admin = User.objects.get(telegram_id=call.message.chat.id)
        ticket = SupportTicket.objects.get(id=ticket_id)

        # Проверка прав: только админы
        if not admin.is_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return

        media_messages = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').order_by('created_at')
        if not media_messages.exists():
            bot.answer_callback_query(call.id, "Файлы не найдены")
            return

        # Инициализируем учет отправленных файлов
        if not getattr(admin, 'received_ticket_files', None):
            admin.received_ticket_files = {}
        ticket_key = str(ticket.id)
        already_sent_ids = set(admin.received_ticket_files.get(ticket_key, []))

        sent = 0
        newly_sent_ids = []
        for msg in media_messages:
            # Пропускаем, если этот файл уже отправлялся этому админу
            if msg.id in already_sent_ids:
                continue
            try:
                caption = msg.caption or f"Файл из обращения #{ticket.id}"
                if msg.content_type == 'photo' and msg.file_id:
                    sent = bot.send_photo(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                elif msg.content_type == 'video' and msg.file_id:
                    sent = bot.send_video(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                elif msg.content_type == 'document' and msg.file_id:
                    sent = bot.send_document(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                else:
                    # На случай неизвестного типа
                    bot.send_message(admin.telegram_id, f"Вложение ({msg.content_type}) без file_id")
                sent += 1
                newly_sent_ids.append(msg.id)
            except Exception as e:
                logger.error(f"Ошибка отправки файла админу {admin.telegram_id}: {e}")
                continue

        # Сохраняем прогресс отправленных файлов
        if newly_sent_ids:
            admin.received_ticket_files[ticket_key] = list(already_sent_ids.union(newly_sent_ids))
            admin.save()

        bot.answer_callback_query(call.id, f"Отправлено новых файлов: {sent}")
    except Exception as e:
        logger.error(f"Ошибка в send_ticket_files_to_admin: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def send_all_ticket_files_to_admin(call: CallbackQuery) -> None:
    """Отправляет админу все файлы из тикета (включая уже отправленные ранее)."""
    try:
        ticket_id = int(call.data.split('_')[-1])
        admin = User.objects.get(telegram_id=call.message.chat.id)
        ticket = SupportTicket.objects.get(id=ticket_id)

        if not admin.is_admin:
            bot.answer_callback_query(call.id, "Нет доступа")
            return

        media_messages = SupportMessage.objects.filter(ticket=ticket).exclude(content_type='text').order_by('created_at')
        if not media_messages.exists():
            bot.answer_callback_query(call.id, "Файлы не найдены")
            return

        sent = 0
        for msg in media_messages:
            try:
                caption = msg.caption or f"Файл из обращения #{ticket.id}"
                if msg.content_type == 'photo' and msg.file_id:
                    sent = bot.send_photo(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                elif msg.content_type == 'video' and msg.file_id:
                    sent = bot.send_video(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                elif msg.content_type == 'document' and msg.file_id:
                    sent = bot.send_document(admin.telegram_id, msg.file_id, caption=caption)
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                else:
                    bot.send_message(admin.telegram_id, f"Вложение ({msg.content_type}) без file_id")
                sent += 1
            except Exception as e:
                logger.error(f"Ошибка отправки файла админу {admin.telegram_id}: {e}")
                continue

        bot.answer_callback_query(call.id, f"Отправлено файлов: {sent}")
    except Exception as e:
        logger.error(f"Ошибка в send_all_ticket_files_to_admin: {e}")
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
        # Переходим в хаб обращений
        from bot.keyboards import get_admin_tickets_hub_markup
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Выберите раздел обращений:",
            reply_markup=get_admin_tickets_hub_markup()
        )

        # На всякий случай очищаем состояние ответа
        if call.message.chat.id in admin_response_state:
            del admin_response_state[call.message.chat.id]

        bot.answer_callback_query(call.id, text=f"❌ Отказ от обращения #{ticket_id}")
    except Exception as e:
        logger.error(f"Ошибка в decline_support_ticket: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def notify_admins_about_new_ticket(ticket: SupportTicket) -> None:
    """Уведомляет только релевантных админов по платформе и супер-админов"""
    try:
        admins = get_relevant_admins_for_ticket(ticket)
        for admin in admins:
            try:
                sent = bot.send_message(
                    chat_id=admin.telegram_id,
                    text=ADMIN_NEW_TICKET_TEXT.format(
                        user_name=ticket.user.user_name,
                        platform=ticket.get_platform_display(),
                        created_at=ticket.created_at.strftime('%H:%M %d.%m.%Y')
                    ),
                    reply_markup=get_admin_ticket_markup(ticket.id)
                )
                _track_admin_message(ticket, admin.telegram_id, sent.message_id)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления админу {admin.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в notify_admins_about_new_ticket: {e}")


def already_assigned_callback(call: CallbackQuery) -> None:
    """Обрабатывает нажатие на кнопку 'уже принято'"""
    bot.answer_callback_query(call.id, ADMIN_TICKET_ALREADY_ASSIGNED_TEXT)


def admin_back_to_tickets(call: CallbackQuery) -> None:
    """Возвращает админа в хаб обращений (свободные / мои / в обработке)"""
    try:
        from bot.keyboards import get_admin_tickets_hub_markup
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Выберите раздел обращений:",
            reply_markup=get_admin_tickets_hub_markup()
        )
        
        # Удаляем состояние ответа админа (но не закрываем обращение)
        if call.message.chat.id in admin_response_state:
            del admin_response_state[call.message.chat.id]
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в admin_back_to_tickets: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def _forward_to_admins(ticket: SupportTicket, message: Message) -> None:
    """Пересылает сообщение пользователя админам с нужными кнопками."""
    admins = []
    if ticket.assigned_admin:
        admins = [ticket.assigned_admin]
    else:
        admins = list(get_relevant_admins_for_ticket(ticket))

    for admin in admins:
        try:
            header = f"Новое сообщение по обращению #{ticket.id} от {ticket.user.user_name}"
            if getattr(message, 'text', None):
                # Если админ назначен на тикет — показываем клавиатуру ответа, иначе — клавиатуру принятия
                if ticket.assigned_admin and ticket.assigned_admin.telegram_id == admin.telegram_id:
                    from bot.keyboards import get_admin_response_markup
                    bot.send_message(admin.telegram_id, f"{header}\n\n{message.text}", reply_markup=get_admin_response_markup(ticket.id))
                else:
                    sent = bot.send_message(admin.telegram_id, f"{header}\n\n{message.text}", reply_markup=get_admin_ticket_markup(ticket.id))
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
            else:
                # Для медиа не пересылаем файл напрямую — пусть будет кнопка "Получить файлы"
                if ticket.assigned_admin and ticket.assigned_admin.telegram_id == admin.telegram_id:
                    from bot.keyboards import get_admin_response_with_files_markup
                    sent = bot.send_message(admin.telegram_id, f"{header}\n\nПолучено вложение. Нажмите, чтобы получить файлы.", reply_markup=get_admin_response_with_files_markup(ticket.id))
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
                else:
                    from bot.keyboards import get_ticket_files_markup
                    sent = bot.send_message(admin.telegram_id, f"{header}\n\nПолучено вложение. Нажмите, чтобы получить файлы.", reply_markup=get_ticket_files_markup(ticket.id))
                    try:
                        _track_admin_message(ticket, admin.telegram_id, sent.message_id)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin.telegram_id}: {e}")


def _notify_admins_user_continues(ticket: SupportTicket) -> None:
    """Уведомляет ТОЛЬКО назначенного админа при возобновлении переписки пользователем.
    Если админ не назначен — не уведомляем никого (во избежание спама)."""
    if not ticket.assigned_admin:
        return
    text = f"Пользователь {ticket.user.user_name} продолжает переписку по обращению #{ticket.id}"
    try:
        # Показываем клавиатуру ответов админа
        from bot.keyboards import get_admin_response_markup
        bot.send_message(ticket.assigned_admin.telegram_id, text, reply_markup=get_admin_response_markup(ticket.id))
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления назначенному админу {ticket.assigned_admin.telegram_id}: {e}")


# ===== НОВЫЕ ФУНКЦИИ ДЛЯ ПОДДЕРЖКИ (АНАЛОГ ГАРАНТИЙНЫХ) =====

def _start_support_questionnaire(user: User, support_request: dict, chat_id: int, with_intro: bool = False, back_callback: str = None) -> None:
    questions_qs = ProductSupportQuestion.objects.filter(product=support_request['product'], is_active=True).order_by('order')
    if not questions_qs.exists():
        _finish_support_questionnaire_and_ask_platform(user, support_request, chat_id)
        return
    questions = list(questions_qs.values_list('id', 'text'))
    support_qna_state[chat_id] = {
        'user_id': user.telegram_id,
        'support_request': support_request,
        'current_question': 0,
        'questions': questions,
        'root_back_callback': back_callback
    }
    prefix_text = "Чтобы оператор помог вам максимально быстро, ответьте, пожалуйста, на несколько вопросов.\n\n" if with_intro else ""
    ask_support_question(chat_id, 0, prefix_text=prefix_text)


def _finish_support_questionnaire_and_ask_platform(user: User, support_request: dict, chat_id: int) -> None:
    """Формирует контекст для поддержки с ответами и показывает выбор платформы."""
    details = [
        "Пользователь оформляет обращение в поддержку.",
    ]
    try:
        if support_request.get('product'):
            details.append(f"Товар: {support_request['product'].name}")
        if support_request.get('issue'):
            details.append(f"Проблема: {support_request['issue'].title}")
        if support_request.get('custom_issue_description'):
            details.append(f"Описание: {support_request['custom_issue_description']}")
        # Добавляем ответы на вопросы
        if support_request.get('answers'):
            details.append("\nОтветы на уточняющие вопросы:")
            for q_text, answer in support_request['answers']:
                details.append(f"- {q_text}\n  Ответ: {answer}")
    except Exception:
        pass
    support_to_support_context[chat_id] = {
        'text': "\n".join(details),
        'answers': support_request.get('answers', [])
    }
    bot.send_message(
        chat_id=chat_id,
        text=(
            "Выберите платформу, где была покупка, чтобы открыть чат поддержки."
        ),
        reply_markup=get_support_platform_markup()
    )


def ask_support_question(chat_id: int, idx: int, prefix_text: str = ''):
    state = support_qna_state.get(chat_id)
    if not state:
        return
    questions = state['questions']
    root_back_callback = state.get('root_back_callback')
    if 0 <= idx < len(questions):
        question_id, question_text = questions[idx]
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('Да', callback_data=f'support_qna_ans_{idx}_yes'),
                   InlineKeyboardButton('Нет', callback_data=f'support_qna_ans_{idx}_no'))
        markup.add(InlineKeyboardButton('⬅️ Назад', callback_data='back_to_main'))
        prefix = prefix_text or ''
        text = f"{prefix}❓ {question_text}"
        bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

def process_support_questionnaire_answer(call: CallbackQuery):
    if not isinstance(call, CallbackQuery):
        return False
    chat_id = call.message.chat.id
    state = support_qna_state.get(chat_id)
    if not state:
        return False
    user = User.objects.get(telegram_id=state['user_id'])
    support_request = state['support_request']
    questions = state['questions']
    idx = state['current_question']
    data = call.data
    if data.startswith('support_qna_ans_'):
        # callback: support_qna_ans_{idx}_yes/no
        parts = data.split('_')
        q_idx = int(parts[3])
        answer = 'Да' if parts[4] == 'yes' else 'Нет'
        question_id, question_text = questions[q_idx]
        if 'answers' not in support_request:
            support_request['answers'] = []
        support_request['answers'].append((question_text, answer))
        next_idx = q_idx + 1
        if next_idx < len(questions):
            state['current_question'] = next_idx
            ask_support_question(chat_id, next_idx)
        else:
            del support_qna_state[chat_id]
            _finish_support_questionnaire_and_ask_platform(user, support_request, chat_id)
    elif data.startswith('support_qna_back_'):
        q_idx = int(data.split('_')[-1])
        prev_idx = q_idx - 1
        if prev_idx >= 0:
            state['current_question'] = prev_idx
            ask_support_question(chat_id, prev_idx)
    bot.answer_callback_query(call.id)


def support_start(call: CallbackQuery) -> None:
    """Начало процесса обращения в поддержку - выбор категории товара"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        
        # Получаем все активные категории товаров
        categories = goods_category.objects.all()
        
        if not categories.exists():
            # Удаляем старое сообщение
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text="😔 К сожалению, категории товаров не найдены.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем клавиатуру с категориями
        markup = InlineKeyboardMarkup()
        for category in categories:
            # Проверяем, есть ли активные товары в категории
            products_count = goods.objects.filter(
                parent_category=category,
                is_active=True
            ).count()
            
            if products_count > 0:
                markup.add(
                    InlineKeyboardButton(
                        f"📦 {category.name}",
                        callback_data=f"support_category_{category.id}"
                    )
                )
        
        # Проверяем, есть ли активные обращения у пользователя
        active_tickets = SupportTicket.objects.filter(
            user=user,
            status__in=['open', 'in_progress']
        ).exists()
        
        if active_tickets:
            markup.add(InlineKeyboardButton("📋 Мои обращения", callback_data="support_my_tickets"))
        
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        text = "🛠️ *Обращение в поддержку*\n\n"
        text += "Выберите категорию товара, с которым у вас возникла проблема:"
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_start: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_select_category(call: CallbackQuery) -> None:
    """Пользователь выбрал категорию - показываем товары"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        category_id = int(call.data.split('_')[-1])
        category = goods_category.objects.get(id=category_id)
        
        # Получаем товары категории
        products = goods.objects.filter(
            parent_category=category,
            is_active=True
        ).order_by('name')
        
        if not products.exists():
            # Удаляем старое сообщение
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text="😔 В этой категории пока нет товаров.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("⬅️ Назад", callback_data="support_start")
                )
            )
            bot.answer_callback_query(call.id)
            return
        
        # Создаем клавиатуру с товарами
        markup = InlineKeyboardMarkup()
        for product in products:
            markup.add(
                InlineKeyboardButton(
                    f"📱 {product.name}",
                    callback_data=f"support_product_{product.id}"
                )
            )
        
        markup.add(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="support_start"
            )
        )
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        text = f"🛠️ *Обращение в поддержку*\n\n"
        text += f"Категория: *{category.name}*\n\n"
        text += "Выберите товар, с которым у вас возникла проблема:"
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_select_category: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_select_product(call: CallbackQuery) -> None:
    """Пользователь выбрал товар - показываем типичные проблемы"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        product_id = int(call.data.split('_')[-1])
        product = goods.objects.get(id=product_id)
        
        # Создаем контекст для поддержки
        support_request = {
            'product': product,
            'user': user
        }
        
        # Получаем типичные проблемы для товара
        issues = TypicalIssue.objects.filter(
            product=product,
            is_active=True
        ).order_by('order', 'title')
        
        # Создаем клавиатуру с проблемами
        markup = InlineKeyboardMarkup()
        
        if issues.exists():
            for issue in issues:
                markup.add(
                    InlineKeyboardButton(
                        f"⚠️ {issue.title}",
                        callback_data=f"support_issue_{issue.id}"
                    )
                )
        
        # Всегда добавляем кнопку "Другое"
        markup.add(
            InlineKeyboardButton(
                "❓ Другое",
                callback_data=f"support_other_{product_id}"
            )
        )
        markup.add(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"support_category_{product.parent_category.id}"
            )
        )
        
        text = f"🛠️ *Обращение в поддержку*\n\n"
        text += f"Товар: *{product.name}*\n\n"
        text += "Выберите проблему, с которой вы столкнулись:"
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_select_product: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_select_issue(call: CallbackQuery) -> None:
    """Пользователь выбрал проблему - показываем решение"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        issue_id = int(call.data.split('_')[-1])
        issue = TypicalIssue.objects.get(id=issue_id)
        
        # Создаем контекст для поддержки
        support_request = {
            'product': issue.product,
            'issue': issue,
            'user': user
        }
        
        # Клавиатура с кнопками
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Помогло", callback_data=f"support_helped_{issue.id}"),
            InlineKeyboardButton("❌ Не помогло", callback_data=f"support_not_helped_{issue.id}")
        )
        markup.add(
            InlineKeyboardButton("⬅️ Назад", callback_data=f"support_product_{issue.product.id}")
        )
        
        # Формируем текст
        text = f"🛠️ *Решение проблемы*\n\n"
        text += f"Товар: *{issue.product.name}*\n"
        text += f"Проблема: *{issue.title}*\n\n"
        
        # Проверяем, есть ли текстовое решение
        has_text = bool(issue.solution_template and issue.solution_template.strip())
        has_file = bool(issue.solution_file)
        
        if has_text:
            # Экранируем специальные символы Markdown для корректного отображения
            solution_text = issue.solution_template.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]').replace('`', '\\`')
            text += f"📝 *Инструкция:*\n\n{solution_text}\n\n"
        
        if has_file:
            text += "📎 *Файл с инструкцией прикреплен ниже*\n\n"
        
        if not has_text and not has_file:
            text += "ℹ️ Решение временно недоступно. Обратитесь к менеджеру.\n\n"
        
        text += "Помогло ли это решение?"
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем текст
        msg = bot.send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        # Если есть файл, отправляем его
        if has_file:
            try:
                with open(issue.solution_file.path, 'rb') as file:
                    bot.send_document(
                        chat_id=call.message.chat.id,
                        document=file,
                        caption=f"📋 Инструкция: {issue.title}"
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки файла решения: {e}")
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_select_issue: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_helped(call: CallbackQuery) -> None:
    """Решение помогло"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        issue_id = int(call.data.split('_')[-1])
        issue = TypicalIssue.objects.get(id=issue_id)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"support_product_{issue.product.id}"))
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=call.message.chat.id,
            text="✅ *Отлично!*\n\n"
                 "Рады, что смогли помочь! 😊\n\n"
                 "Если возникнут другие вопросы - обращайтесь!",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "Спасибо за обратную связь!")
        
    except Exception as e:
        logger.error(f"Ошибка в support_helped: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_not_helped(call: CallbackQuery) -> None:
    """Решение не помогло - переходим к анкете"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        issue_id = int(call.data.split('_')[-1])
        issue = TypicalIssue.objects.get(id=issue_id)
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Создаем контекст для поддержки
        support_request = {
            'product': issue.product,
            'issue': issue,
            'user': user
        }
        
        # Проверяем, есть ли активные вопросы
        questions = ProductSupportQuestion.objects.filter(product=support_request['product'], is_active=True).order_by('order')
        if questions.exists():
            # Начинаем анкету с интро и кнопками 'Да', 'Нет', 'Назад'
            _start_support_questionnaire(user, support_request, call.message.chat.id, with_intro=True, back_callback=f"support_product_{issue.product.id}")
        else:
            # Нет вопросов, сразу переходим к выбору платформы
            _finish_support_questionnaire_and_ask_platform(user, support_request, call.message.chat.id)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_not_helped: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")


def support_other(call: CallbackQuery) -> None:
    """Пользователь выбрал "Другое" - переходим к анкете"""
    try:
        user = User.objects.get(telegram_id=call.message.chat.id)
        product_id = int(call.data.split('_')[-1])
        product = goods.objects.get(id=product_id)
        
        # Удаляем старое сообщение
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Создаем контекст для поддержки
        support_request = {
            'product': product,
            'user': user
        }
        
        # Проверяем, есть ли активные вопросы
        questions = ProductSupportQuestion.objects.filter(product=support_request['product'], is_active=True).order_by('order')
        if questions.exists():
            # Начинаем анкету с интро и кнопками 'Да', 'Нет', 'Назад'
            _start_support_questionnaire(user, support_request, call.message.chat.id, with_intro=True, back_callback=f"support_product_{product.id}")
        else:
            # Нет вопросов, сразу переходим к выбору платформы
            _finish_support_questionnaire_and_ask_platform(user, support_request, call.message.chat.id)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка в support_other: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка. Попробуйте позже.")
