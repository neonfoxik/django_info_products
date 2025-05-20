# Этот файл оставлен пустым, так как функциональность cron была удалена

# Функции для регулярного выполнения задач
import logging
from django.utils import timezone
from bot.models import User
from bot import bot
import json

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
