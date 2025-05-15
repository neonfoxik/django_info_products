# Этот файл оставлен пустым, так как функциональность cron была удалена

# Функции для регулярного выполнения задач
import logging
from django.utils import timezone
from bot.models import User

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
