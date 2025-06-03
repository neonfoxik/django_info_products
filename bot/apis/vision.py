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

def analyze_screenshot(photo: PhotoSize, bot, product_id=None) -> dict:
    """
    Анализирует скриншот на наличие 5-звездочного отзыва, даты и соответствие товару
    
    Args:
        photo: Объект фотографии из Telegram
        bot: Объект бота для скачивания файла
        product_id: ID товара для проверки соответствия
    
    Returns:
        dict: Результат анализа с ключами 'success', 'has_5_stars', 'message', 'confidence', 
              'stars_count', 'review_date', 'product_match', 'is_returned', 'has_multiple_products'
    """
    try:
        # Получаем файл из Telegram
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Если передан product_id, получаем изображение товара
        product_image = None
        if product_id:
            from bot.models import goods
            try:
                product = goods.objects.get(id=product_id)
                if product.image:
                    product_image = product.image.path
            except goods.DoesNotExist:
                pass
        
        # Пробуем сначала использовать более легкую модель для экономии токенов
        try:
            # Кодируем файл в base64 для передачи в API
            base64_image = base64.b64encode(downloaded_file).decode('utf-8')
            
            # Формируем системное сообщение
            system_message = "Определи количество желтых звезд в отзыве и дату отзыва. "
            if product_image:
                system_message += "Также проверь, соответствует ли отзыв изображенному товару. "
            system_message += "Если желтых звезд меньше 5, укажи точное количество. Если 5 желтых звезд, напиши '5 звезд'. "
            system_message += "Если желтых звезд нет или это не отзыв, напиши 'нет звезд'. "
            system_message += "Если видишь дату отзыва, укажи её в формате ДД.ММ.ГГГГ. "
            system_message += "Если дат несколько, используй последнюю (нижнюю) дату. "
            system_message += "Если даты нет, напиши 'нет даты'. "
            system_message += "Если товаров несколько, напиши 'несколько товаров'. "
            system_message += "Если товар возвращен или отменен, напиши 'товар возвращен'. "
            if product_image:
                system_message += "Если товар соответствует, напиши 'товар соответствует'. "
                system_message += "Если не соответствует, напиши 'товар не соответствует'."
            
            messages = [
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Проанализируй отзыв и товар. Отвечай кратко: количество желтых звезд, дата в формате "
                                    "ДД.ММ.ГГГГ или 'нет даты', и соответствие товара если указано. "
                                    "Если товар возвращен или отменен, укажи это. "
                                    "Если дат несколько, используй последнюю."
                                    "Если товаров несколько, то направляй на переотправку скриншота."
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
            
            # Если есть изображение товара, добавляем его в запрос
            if product_image:
                with open(product_image, 'rb') as img_file:
                    product_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    messages[1]["content"].append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{product_base64}"
                        }
                    })
            
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
            date_matches = re.findall(r'(\d{2}\.\d{2}\.\d{4})', answer)
            if date_matches:
                # Берем последнюю дату из списка
                review_date = date_matches[-1]

            # Определяем, возвращен ли товар
            is_returned = "товар возвращен" in answer_lower or "товар отменен" in answer_lower

            # Определяем соответствие товара
            product_match = None
            if product_image:
                if "товар соответствует" in answer_lower:
                    product_match = True
                elif "товар не соответствует" in answer_lower:
                    product_match = False

            # Проверяем наличие нескольких товаров
            has_multiple_products = "несколько товаров" in answer_lower

            # Определяем уверенность
            confidence = 0
            confidence_match = re.search(r'(\d{1,3})%', answer)
            if confidence_match:
                confidence = int(confidence_match.group(1))
            elif stars_count > 0:
                confidence = 80
            
            # Формируем сообщение в зависимости от результатов
            message_parts = []

            if is_returned:
                message_parts.append("Товар возвращен или отменен. Расширенная гарантия недоступна.")
                has_5_stars = False
            elif has_multiple_products:
                message_parts.append("На скриншоте обнаружено несколько товаров. Пожалуйста, отправьте скриншот только с одним товаром.")
                has_5_stars = False
            elif stars_count == 5:
                message_parts.append("Отзыв с 5 звездами подтвержден!")
                has_5_stars = True
            elif stars_count > 0:
                message_parts.append(f"В отзыве обнаружено {stars_count} звезд. Для получения расширенной гарантии необходимо оставить отзыв с 5 звездами.")
                has_5_stars = False
            else:
                message_parts.append("Не удалось обнаружить звезды в отзыве. Пожалуйста, убедитесь, что на скриншоте отображается отзыв с рейтингом.")
                has_5_stars = False

            if product_image and not is_returned and not has_multiple_products:
                if product_match is True:
                    message_parts.append("Товар в отзыве соответствует запрошенному.")
                elif product_match is False:
                    message_parts.append("Товар в отзыве не соответствует запрошенному. Пожалуйста, отправьте скриншот отзыва правильного товара.")
                    has_5_stars = False

            message = " ".join(message_parts)
            
            return {
                'success': True,
                'has_5_stars': has_5_stars,
                'message': message,
                'confidence': confidence,
                'stars_count': stars_count,
                'review_date': review_date,
                'product_match': product_match,
                'is_returned': is_returned,
                'has_multiple_products': has_multiple_products
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
                'review_date': None,
                'product_match': None,
                'is_returned': False,
                'has_multiple_products': False
            }
            
    except Exception as e:
        logger.error(f"[VISION] Ошибка при анализе скриншота: {e}")
        return {
            'success': False,
            'has_5_stars': False,
            'message': f"Не удалось проанализировать изображение. Пожалуйста, отправьте более четкий скриншот с 5-звездочным отзывом.",
            'confidence': 0,
            'stars_count': 0,
            'review_date': None,
            'product_match': None,
            'is_returned': False,
            'has_multiple_products': False
        } 