# Этот файл оставлен пустым, так как функциональность cron была удалена

# Функции для регулярного выполнения задач
import logging
from django.utils import timezone
from bot.models import User, SupportTicket, OwnerSettings
from bot.texts import ADMIN_REMINDER_TEXT, OWNER_NOTIFICATION_TEXT
from bot.keyboards import get_admin_ticket_markup
from bot import bot
import json
from datetime import timedelta

logger = logging.getLogger(__name__)

def reset_screenshot_counters():
    """
    Сбрасывает счетчики скриншотов пользователей ежедневно
    Функция вызывается из cron-задачи один раз в день (обычно в полночь)
    """
    try:
        today = timezone.now().date()
        
        # Получаем всех пользователей, у которых счетчик скриншотов > 0
        users_with_screenshots = User.objects.filter(screenshots_count__gt=0)
        
        # Сбрасываем счетчики
        counter = 0
        for user in users_with_screenshots:
            user.screenshots_count = 0
            user.last_screenshot_date = today
            user.save()
            counter += 1
        
        logger.info(f"[CRON] Сброшены счетчики скриншотов для {counter} пользователей")
        return f"Сброшены счетчики скриншотов для {counter} пользователей"
    
    except Exception as e:
        logger.error(f"[CRON] Ошибка при сбросе счетчиков скриншотов: {e}")
        return f"Ошибка при сбросе счетчиков скриншотов: {e}"

def check_warranty_expiration():
    """
    Проверяет истечение срока расширенной гарантии
    Функция вызывается из cron-задачи ежедневно
    """
    try:
        current_date = timezone.now()
        users_with_warranty = User.objects.filter(extended_warranty_products__isnull=False)
        
        expired_count = 0
        for user in users_with_warranty:
            extended_warranty_info = user.extended_warranty_info or {}
            if isinstance(extended_warranty_info, str):
                extended_warranty_info = json.loads(extended_warranty_info)
            
            expired_products = []
            for product_id, info in extended_warranty_info.items():
                try:
                    end_date = timezone.datetime.strptime(info['end_date'], "%d.%m.%Y")
                    if current_date > end_date:
                        expired_products.append(info['name'])
                except (ValueError, KeyError):
                    continue
            
            if expired_products:
                # Отправляем уведомление пользователю
                message = (
                    "⚠️ Уведомление об истечении срока гарантии\n\n"
                    "Срок расширенной гарантии истек для следующих товаров:\n"
                )
                for product in expired_products:
                    message += f"• {product}\n"
                
                try:
                    bot.send_message(
                        chat_id=user.telegram_id,
                        text=message
                    )
                    expired_count += 1
                except Exception as e:
                    logger.error(f"[CRON] Ошибка при отправке уведомления пользователю {user.telegram_id}: {e}")
        
        logger.info(f"[CRON] Отправлены уведомления о истечении гарантии для {expired_count} пользователей")
        return f"Отправлены уведомления о истечении гарантии для {expired_count} пользователей"
    
    except Exception as e:
        logger.error(f"[CRON] Ошибка при проверке истечения срока гарантии: {e}")
        return f"Ошибка при проверке истечения срока гарантии: {e}"


def check_support_notifications():
    """
    Проверяет необработанные обращения и отправляет уведомления
    Функция вызывается каждую минуту
    """
    try:
        current_time = timezone.now()
        notifications_sent = 0
        
        # Получаем все открытые обращения
        open_tickets = SupportTicket.objects.filter(status='open')
        
        for ticket in open_tickets:
            # Проверяем первое уведомление (через 5 минут)
            if (not ticket.first_admin_notification_sent and 
                current_time - ticket.created_at >= timedelta(minutes=5)):
                
                send_admin_reminder(ticket, is_first=True)
                ticket.first_admin_notification_sent = current_time
                ticket.save()
                notifications_sent += 1
            
            # Проверяем второе уведомление (через 10 минут от создания, если первое уже отправлено)
            elif (ticket.first_admin_notification_sent and 
                  not ticket.second_admin_notification_sent and 
                  current_time - ticket.created_at >= timedelta(minutes=10)):
                
                send_admin_reminder(ticket, is_first=False)
                ticket.second_admin_notification_sent = current_time
                ticket.save()
                notifications_sent += 1
            
            # Проверяем уведомление владельцу (через 15 минут от создания)
            elif (ticket.second_admin_notification_sent and 
                  not ticket.owner_notification_sent and 
                  current_time - ticket.created_at >= timedelta(minutes=15)):
                
                send_owner_notification(ticket)
                ticket.owner_notification_sent = current_time
                ticket.save()
                notifications_sent += 1
        
        if notifications_sent > 0:
            logger.info(f"[CRON] Отправлено {notifications_sent} уведомлений о необработанных обращениях")
        
        return f"Отправлено {notifications_sent} уведомлений о необработанных обращениях"
    
    except Exception as e:
        logger.error(f"[CRON] Ошибка при проверке уведомлений поддержки: {e}")
        return f"Ошибка при проверке уведомлений поддержки: {e}"


def send_admin_reminder(ticket: SupportTicket, is_first: bool = True):
    """Отправляет напоминание админам о необработанном обращении"""
    try:
        admins = User.objects.filter(is_admin=True)
        
        for admin in admins:
            try:
                bot.send_message(
                    chat_id=admin.telegram_id,
                    text=ADMIN_REMINDER_TEXT.format(
                        ticket_id=ticket.id,
                        user_name=ticket.user.user_name,
                        platform=ticket.get_platform_display()
                    ),
                    reply_markup=get_admin_ticket_markup(ticket.id)
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания админу {admin.telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в send_admin_reminder: {e}")


def send_owner_notification(ticket: SupportTicket):
    """Отправляет критическое уведомление владельцу"""
    try:
        owners = OwnerSettings.objects.filter(is_active=True)
        
        for owner in owners:
            try:
                bot.send_message(
                    chat_id=owner.owner_telegram_id,
                    text=OWNER_NOTIFICATION_TEXT.format(
                        ticket_id=ticket.id,
                        user_name=ticket.user.user_name,
                        platform=ticket.get_platform_display()
                    ),
                    reply_markup=get_admin_ticket_markup(ticket.id)
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления владельцу {owner.owner_telegram_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка в send_owner_notification: {e}")


def clean_old_tickets():
    """
    Очищает старые закрытые обращения (старше 30 дней)
    Функция вызывается ежедневно
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        old_tickets = SupportTicket.objects.filter(
            status='closed',
            closed_at__lt=cutoff_date
        )
        
        deleted_count = old_tickets.count()
        old_tickets.delete()
        
        logger.info(f"[CRON] Удалено {deleted_count} старых обращений")
        return f"Удалено {deleted_count} старых обращений"
    
    except Exception as e:
        logger.error(f"[CRON] Ошибка при очистке старых обращений: {e}")
        return f"Ошибка при очистке старых обращений: {e}"
