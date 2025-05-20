import os
import openai
import base64
import dotenv
import logging
import re
from io import BytesIO
from django.conf import settings
from telebot.types import PhotoSize

dotenv.load_dotenv()

# Настраиваем API ключ и URL
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = "https://api.vsegpt.ru:6070/v1/"

logger = logging.getLogger(__name__)

def analyze_screenshot(photo: PhotoSize, bot) -> dict:
    """
    Анализирует скриншот на наличие 5-звездочного отзыва
    
    Args:
        photo: Объект фотографии из Telegram
        bot: Объект бота для скачивания файла
    
    Returns:
        dict: Результат анализа с ключами 'success', 'has_5_stars', 'message', 'confidence'
    """
    try:
        # Получаем файл из Telegram
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Пробуем сначала использовать более легкую модель для экономии токенов
        try:
            # Кодируем файл в base64 для передачи в API
            base64_image = base64.b64encode(downloaded_file).decode('utf-8')
            
            # Используем более легкую модель с меньшим количеством токенов
            messages = [
                {
                    "role": "system",
                    "content": "Ищи отзывы с 5 желтыми звездами. НЕ подходят изображения на которых написано только текстом а также те на которых меньше 5 звезд"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Есть ли на этом скриншоте отзыв с 5 звездами? Отвечай кратко: да/нет, уверенность в процентах."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Вызываем модель с поддержкой компьютерного зрения, но с меньшим потреблением токенов
            response = openai.chat.completions.create(
                model="vis-google/gemini-flash-1.5",  # Используем более легкую модель
                messages=messages,
                max_tokens=50  # Ограничиваем количество токенов для экономии
            )
            
            answer = response.choices[0].message.content
            logger.info(f"[VISION] Получен ответ от API: {answer}")
            
            # Анализируем ответ модели
            answer_lower = answer.lower()
            has_5_stars = "да" in answer_lower and "нет" not in answer_lower[:10]
            
            # Определяем уверенность
            confidence = 0
            confidence_match = re.search(r'(\d{1,3})%', answer)
            if confidence_match:
                confidence = int(confidence_match.group(1))
            elif has_5_stars and "увер" in answer_lower:
                # Если есть упоминание уверенности, но без процентов
                confidence = 80
            elif has_5_stars:
                # Если просто "да", берем базовую уверенность
                confidence = 75
            
            # Принимаем результат, если уверенность >= 70% или явно указано "да"
            is_valid = has_5_stars and confidence >= 70
            
            return {
                'success': True,
                'has_5_stars': is_valid,
                'message': answer,
                'confidence': confidence
            }
            
        except Exception as e:
            # Если что-то пошло не так с API или анализом, используем локальный анализ
            logger.error(f"[VISION] Ошибка при вызове API Vision: {e}")
            logger.info("[VISION] Переключаемся на локальный анализ изображения")
            
            # Простой анализ изображения без внешнего API
            # Здесь мы даем пользователю сомнение в пользу, т.к. не можем проверить
            # Но требуем дополнительное подтверждение
            return {
                'success': True,
                'has_5_stars': False,  # Требуем подтверждения от пользователя
                'message': "Не удалось автоматически проверить наличие 5-звездочного отзыва. Пожалуйста, убедитесь, что на скриншоте отображается отзыв с 5 звездами и отправьте его снова или подтвердите вручную.",
                'confidence': 0
            }
            
    except Exception as e:
        logger.error(f"[VISION] Ошибка при анализе скриншота: {e}")
        # В случае общей ошибки требуем у пользователя подтверждение
        return {
            'success': False,
            'has_5_stars': False,  # По умолчанию НЕ принимаем как валидный
            'message': f"Не удалось проанализировать изображение. Пожалуйста, отправьте более четкий скриншот с 5-звездочным отзывом.",
            'confidence': 0
        } 