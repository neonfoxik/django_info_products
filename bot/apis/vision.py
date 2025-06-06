import os
import openai
import base64
import dotenv
import logging
import re
from io import BytesIO
from django.conf import settings
from telebot.types import PhotoSize
import io
import numpy as np
import cv2
from PIL import Image

dotenv.load_dotenv()

# Настраиваем API ключ и URL
openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = "https://api.vsegpt.ru:6070/v1/"

logger = logging.getLogger(__name__)

def analyze_screenshot(photo: PhotoSize, bot, product_id=None) -> dict:
    """
    Анализирует скриншот отзыва на наличие 5 желтых звезд и соответствие товару.
    
    Args:
        photo: Объект PhotoSize с информацией о фотографии
        bot: Объект бота для отправки сообщений
        product_id: ID товара для проверки соответствия
        
    Returns:
        dict: Результат анализа с полями:
            - has_5_stars: bool - есть ли 5 желтых звезд
            - confidence: float - уверенность в определении (0-100)
            - stars_count: int - количество найденных звезд
            - review_date: str - дата отзыва (если определена)
            - product_match: bool - соответствует ли товар
            - message: str - сообщение с результатом проверки
    """
    try:
        # Получаем файл фотографии
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Конвертируем изображение в формат для анализа
        image = Image.open(io.BytesIO(downloaded_file))
        
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Преобразуем в numpy array
        image_np = np.array(image)
        
        # Определяем диапазон желтого цвета в HSV
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])
        
        # Конвертируем изображение в HSV
        hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
        
        # Создаем маску для желтого цвета
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # Находим контуры желтых объектов
        contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Фильтруем контуры по размеру и форме для поиска звезд
        stars = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 100 < area < 1000:  # Размер звезды
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = float(w)/h
                if 0.8 < aspect_ratio < 1.2:  # Звезда должна быть примерно квадратной
                    stars.append((x, y, w, h))
        
        # Сортируем звезды по координате x
        stars.sort(key=lambda x: x[0])
        
        # Проверяем количество звезд
        stars_count = len(stars)
        has_5_stars = stars_count == 5
        
        # Рассчитываем уверенность
        confidence = min(100, (stars_count / 5) * 100)
        
        # Проверяем соответствие товару, если указан product_id
        product_match = None
        if product_id:
            try:
                product = goods.objects.get(id=product_id)
                # Здесь можно добавить дополнительную логику проверки соответствия товара
                # Например, поиск названия товара на скриншоте
                product_match = True  # Временно всегда True
            except goods.DoesNotExist:
                product_match = False
        
        # Формируем сообщение
        if has_5_stars:
            message = "✅ Отзыв содержит 5 желтых звезд!"
        else:
            message = "❌ Отзыв должен содержать 5 желтых звезд."
        
        return {
            'has_5_stars': has_5_stars,
            'confidence': confidence,
            'stars_count': stars_count,
            'review_date': None,  # Можно добавить определение даты
            'product_match': product_match,
            'message': message
        }
        
    except Exception as e:
        print(f"[ERROR] Ошибка при анализе скриншота: {e}")
        logger.error(f"[ERROR] Ошибка при анализе скриншота: {e}")
        return {
            'has_5_stars': False,
            'confidence': 0,
            'stars_count': 0,
            'review_date': None,
            'product_match': None,
            'message': "Произошла ошибка при анализе скриншота."
        } 