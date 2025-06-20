import os
from openai import OpenAI
import base64
import dotenv
import logging
import re
from io import BytesIO
from django.conf import settings
from telebot.types import PhotoSize

dotenv.load_dotenv()

# Инициализируем клиент OpenAI с API ключом и базовым URL
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.vsegpt.ru:6070/v1/"
)

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
        
        # Если передан product_id, пытаемся получить изображение товара (если оно есть)
        product_image = None
        product_name = None
        if product_id:
            from bot.models import goods
            try:
                product = goods.objects.get(id=product_id)
                product_name = product.name
                # Проверяем наличие изображений товара
                if product.images.exists():
                    product_image = product.images.first().image.path
            except goods.DoesNotExist:
                pass
        
        # Пробуем сначала использовать более легкую модель для экономии токенов
        try:
            # Кодируем файл в base64 для передачи в API
            base64_image = base64.b64encode(downloaded_file).decode('utf-8')
            
            # Формируем системное сообщение
            system_message = "Определи количество желтых звезд в отзыве и дату отзыва. "
            if product_image:
                system_message += f"КРИТИЧНО: Сравни товар на скриншоте с товаром '{product_name}'. "
                system_message += "Товары должны быть ОДИНАКОВЫМИ по типу, внешнему виду и функциональности. "
                system_message += "Если товары РАЗНЫЕ (например, кроссовки vs гирлянда, телефон vs наушники), то это НЕ соответствие. "
                system_message += "Обрати внимание на: цвет, форму, размер, тип товара, бренд, модель. "
            system_message += "Если желтых звезд меньше 5, укажи точное количество. Если 5 желтых звезд, напиши '5 звезд'. "
            system_message += "Если желтых звезд нет или это не отзыв, напиши 'нет звезд'. "
            system_message += "Если видишь дату отзыва, укажи её в формате ДД.ММ.ГГГГ. "
            system_message += "Если дат несколько, используй последнюю (нижнюю) дату. "
            system_message += "Если даты нет, напиши 'нет даты'. "
            system_message += "Если товаров несколько, напиши 'несколько товаров'. "
            system_message += "Если товар возвращен или отменен, напиши 'товар возвращен'. "
            if product_image:
                system_message += "Если товары ОДИНАКОВЫЕ, напиши 'товар соответствует'. "
                system_message += "Если товары РАЗНЫЕ, напиши 'товар не соответствует'. "
                system_message += "Если не уверен в сравнении, напиши 'не могу определить'."
            
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
                            "text": "ВНИМАТЕЛЬНО проанализируй отзыв и сравни товары. "
                                    "Отвечай кратко: количество желтых звезд, дата в формате "
                                    "ДД.ММ.ГГГГ или 'нет даты', и точное соответствие товара. "
                                    "Если товар возвращен или отменен, укажи это. "
                                    "Если дат несколько, используй последнюю. "
                                    "Если товаров несколько, то направляй на переотправку скриншота. "
                                    "При сравнении товаров будь СТРОГИМ - товары должны быть ОДИНАКОВЫМИ."
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
            response = client.chat.completions.create(
                model="vis-qwen/qwen2.5-vl-72b-instruct",
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
                    logger.info(f"[VISION] Товар соответствует: {product_name}")
                elif "товар не соответствует" in answer_lower or "не могу определить" in answer_lower:
                    product_match = False
                    logger.info(f"[VISION] Товар НЕ соответствует: {product_name}")
                else:
                    # Если AI не дал четкого ответа о соответствии, считаем что товары не соответствуют
                    product_match = False
                    logger.warning(f"[VISION] Неопределенное соответствие товара: {product_name}, считаем как НЕ соответствует")

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
            has_5_stars = False

            # ПЕРВЫЙ ЭТАП: Проверяем базовые условия (звезды и возврат товара)
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

            # ВТОРОЙ ЭТАП: Если базовые условия пройдены, проверяем соответствие товара
            if has_5_stars and not is_returned and not has_multiple_products and product_image:
                if product_match is True:
                    message_parts.append("Товар в отзыве соответствует запрошенному.")
                elif product_match is False:
                    message_parts.append(f"❌ Товар в отзыве НЕ соответствует запрошенному товару '{product_name}'. Пожалуйста, убедитесь, что вы отправляете скриншот отзыва именно этого товара.")
                    has_5_stars = False  # КРИТИЧНО: Блокируем активацию если товары не похожи
                elif product_match is None:
                    # Если AI не смог определить соответствие, но у товара есть изображение
                    message_parts.append(f"❓ Не удалось определить соответствие товара '{product_name}'. Пожалуйста, убедитесь, что отправляете скриншот отзыва правильного товара.")
                    has_5_stars = False  # КРИТИЧНО: Блокируем активацию если не можем определить соответствие

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