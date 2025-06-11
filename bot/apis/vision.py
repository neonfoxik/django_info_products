import os
from openai import OpenAI
import base64
import dotenv
import logging
import re
import json
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
        if product_id:
            from bot.models import goods
            try:
                product = goods.objects.get(id=product_id)
                # Проверяем наличие primary_image (если есть связь)
                if hasattr(product, 'primary_image') and product.primary_image and hasattr(product.primary_image, 'image'):
                    product_image = product.primary_image.image.path
            except goods.DoesNotExist:
                pass
        
        # Пробуем сначала использовать более легкую модель для экономии токенов
        try:
            # Кодируем файл в base64 для передачи в API
            base64_image = base64.b64encode(downloaded_file).decode('utf-8')
            
            # Формируем системное сообщение
            system_message = """Ты эксперт по анализу скриншотов отзывов с маркетплейсов (Wildberries, OZON, Яндекс.Маркет и др.).

ТВОЯ ЗАДАЧА: Проанализировать скриншот и определить:
1. Точное количество желтых/золотистых звезд в рейтинге отзыва (1-5)
2. Дату написания отзыва 
3. Статус заказа (возврат/отмена)
4. Количество товаров на скриншоте
5. Соответствие товара (если предоставлено эталонное изображение)

ВАЖНЫЕ ДЕТАЛИ:
- Звезды могут быть желтыми, золотистыми или оранжевыми
- Ищи звезды именно в разделе ОТЗЫВА, не в общем рейтинге товара
- Игнорируй пустые/серые звезды - считай только закрашенные
- Дата может быть в форматах: ДД.ММ.ГГГГ, ДД месяц ГГГГ, ДД/ММ/ГГГГ
- Статусы возврата: "Возвращен", "Отменен", "Возврат", "Отмена", "Возвращено"
- Если несколько дат - выбирай дату отзыва, а не заказа/доставки
- Если видишь список товаров или корзину - это несколько товаров
- Внимательно различай товары и их вариации (размер, цвет)

КРИТИЧЕСКИ ВАЖНО:
- НЕ путай общий рейтинг товара с рейтингом конкретного отзыва
- Ищи звезды рядом с текстом отзыва или аватаром пользователя
- Если сомневаешься в количестве звезд - укажи 0 и объясни в details

ОТВЕЧАЙ СТРОГО В JSON ФОРМАТЕ:
{
  "stars": число_от_0_до_5,
  "date": "ДД.ММ.ГГГГ" или null,
  "is_returned": true/false,
  "multiple_products": true/false,
  "product_matches": true/false/null,
  "confidence": число_от_0_до_100,
  "details": "краткое_объяснение"
}"""

            user_message = """Проанализируй этот скриншот отзыва и верни результат в указанном JSON формате.

ПОШАГОВЫЙ АНАЛИЗ:
1. Найди секцию с отзывами (не общий рейтинг товара)
2. Подсчитай закрашенные желтые/золотистые звезды в отзыве
3. Найди дату рядом с отзывом (обычно под именем пользователя)
4. Проверь статус заказа/товара
5. Оцени количество разных товаров на экране

Будь максимально внимательным к деталям!"""

            if product_image:
                user_message += "\n\nТакже сравни товар в отзыве с эталонным изображением товара и определи их соответствие."
            
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
                            "text": user_message
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
                max_tokens=200,
                temperature=0.1
            )
            
            answer = response.choices[0].message.content
            logger.info(f"[VISION] Получен ответ от API: {answer}")
            
            # Парсим JSON ответ
            try:
                # Извлекаем JSON из ответа (на случай если есть дополнительный текст)
                json_match = re.search(r'\{.*?\}', answer, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                else:
                    json_str = answer
                
                result = json.loads(json_str)
                
                # Извлекаем данные из JSON ответа
                stars_count = result.get('stars', 0)
                review_date = result.get('date')
                is_returned = result.get('is_returned', False)
                has_multiple_products = result.get('multiple_products', False)
                product_match = result.get('product_matches')
                confidence = result.get('confidence', 0)
                details = result.get('details', '')
                
                # Валидация данных
                if not isinstance(stars_count, int) or stars_count < 0 or stars_count > 5:
                    stars_count = 0
                if not isinstance(confidence, int) or confidence < 0 or confidence > 100:
                    confidence = 0 if stars_count == 0 else 80
                
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
                    'has_multiple_products': has_multiple_products,
                    'details': details
                }
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"[VISION] Ошибка парсинга JSON ответа: {e}. Ответ: {answer}")
                
                # Фоллбэк - пытаемся парсить старым способом
                answer_lower = answer.lower()
                
                # Определяем количество звезд
                stars_count = 0
                if "5 звезд" in answer_lower or "5 звезды" in answer_lower or '"stars": 5' in answer_lower:
                    stars_count = 5
                else:
                    stars_match = re.search(r'(\d+)', answer)
                    if stars_match:
                        stars_count = min(int(stars_match.group(1)), 5)
                
                # Определяем дату отзыва
                review_date = None
                date_matches = re.findall(r'(\d{2}\.\d{2}\.\d{4})', answer)
                if date_matches:
                    review_date = date_matches[-1]

                # Определяем остальные параметры
                is_returned = any(keyword in answer_lower for keyword in ['возврат', 'отмен', 'returned', 'cancel'])
                has_multiple_products = any(keyword in answer_lower for keyword in ['несколько товаров', 'multiple_products'])
                
                product_match = None
                if product_image:
                    if any(keyword in answer_lower for keyword in ['соответствует', 'matches": true']):
                        product_match = True
                    elif any(keyword in answer_lower for keyword in ['не соответствует', 'matches": false']):
                        product_match = False
                
                confidence = 80 if stars_count > 0 else 0
                details = "Использован резервный парсинг из-за ошибки JSON"
                
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
                    'has_multiple_products': has_multiple_products,
                    'details': details
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
                'has_multiple_products': False,
                'details': f"Не удалось автоматически проверить наличие 5-звездочного отзыва. Пожалуйста, убедитесь, что на скриншоте отображается отзыв с 5 звездами и отправьте его снова или подтвердите вручную."
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
            'has_multiple_products': False,
            'details': f"Не удалось проанализировать изображение. Пожалуйста, отправьте более четкий скриншот с 5-звездочным отзывом. Ошибка: {e}"
        } 