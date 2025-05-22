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
    Анализирует скриншот на наличие 5-звездочного отзыва и даты
    
    Args:
        photo: Объект фотографии из Telegram
        bot: Объект бота для скачивания файла
    
    Returns:
        dict: Результат анализа с ключами 'success', 'has_5_stars', 'message', 'confidence', 'stars_count', 'review_date'
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
                    "content": "Определи количество звезд в отзыве и дату отзыва. Если звезд меньше 5, укажи точное количество. Если 5 звезд, напиши '5 звезд'. Если звезд нет или это не отзыв, напиши 'нет звезд'. Если видишь дату отзыва, укажи её в формате ДД.ММ.ГГГГ. Если даты нет, напиши 'нет даты'."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Сколько звезд в этом отзыве и какая дата отзыва? Отвечай кратко: количество звезд и дата в формате ДД.ММ.ГГГГ или 'нет даты'."
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
            
            # Вызываем модель с поддержкой компьютерного зрения
            response = openai.chat.completions.create(
                model="vis-google/gemini-flash-1.5",
                messages=messages,
                max_tokens=100
            )
            
            answer = response.choices[0].message.content
            logger.info(f"[VISION] Получен ответ от API: {answer}")
            
            # Анализируем ответ модели
            answer_lower = answer.lower()
            
            # Определяем количество звезд
            stars_count = 0
            if "5 звезд" in answer_lower or "5 звезды" in answer_lower:
                stars_count = 5
            else:
                # Ищем число в ответе
                stars_match = re.search(r'(\d+)', answer)
                if stars_match:
                    stars_count = int(stars_match.group(1))
            
            # Определяем дату отзыва
            review_date = None
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', answer)
            if date_match:
                review_date = date_match.group(1)
            
            # Определяем уверенность
            confidence = 0
            confidence_match = re.search(r'(\d{1,3})%', answer)
            if confidence_match:
                confidence = int(confidence_match.group(1))
            elif stars_count > 0:
                confidence = 80
            
            # Формируем сообщение в зависимости от количества звезд
            if stars_count == 5:
                message = "Отзыв с 5 звездами подтвержден!"
                has_5_stars = True
            elif stars_count > 0:
                message = f"В отзыве обнаружено {stars_count} звезд. Для получения расширенной гарантии необходимо оставить отзыв с 5 звездами."
                has_5_stars = False
            else:
                message = "Не удалось обнаружить звезды в отзыве. Пожалуйста, убедитесь, что на скриншоте отображается отзыв с рейтингом."
                has_5_stars = False
            
            return {
                'success': True,
                'has_5_stars': has_5_stars,
                'message': message,
                'confidence': confidence,
                'stars_count': stars_count,
                'review_date': review_date
            }
            
        except Exception as e:
            logger.error(f"[VISION] Ошибка при вызове API Vision: {e}")
            logger.info("[VISION] Переключаемся на локальный анализ изображения")
            
            return {
                'success': True,
                'has_5_stars': False,
                'message': "Не удалось автоматически проверить наличие 5-звездочного отзыва. Пожалуйста, убедитесь, что на скриншоте отображается отзыв с 5 звездами и отправьте его снова или подтвердите вручную.",
                'confidence': 0,
                'stars_count': 0,
                'review_date': None
            }
            
    except Exception as e:
        logger.error(f"[VISION] Ошибка при анализе скриншота: {e}")
        return {
            'success': False,
            'has_5_stars': False,
            'message': f"Не удалось проанализировать изображение. Пожалуйста, отправьте более четкий скриншот с 5-звездочным отзывом.",
            'confidence': 0,
            'stars_count': 0,
            'review_date': None
        } 