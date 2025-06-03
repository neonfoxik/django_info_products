import os
from datetime import datetime
from django.utils import timezone
import logging
import pandas as pd  # Добавляем импорт pandas

logger = logging.getLogger(__name__)

class WarrantyExcelHandler:
    def __init__(self):
        self.file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'warranty_records.xlsx')
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Создает файл Excel, если он не существует"""
        try:
            if not os.path.exists(self.file_path):
                df = pd.DataFrame(columns=[
                    'Дата активации',
                    'ID пользователя',
                    'Имя пользователя',
                    'ID товара',
                    'Название товара',
                    'Срок гарантии',
                    'Дата окончания',
                    'Дата отзыва',
                    'ID скриншота',
                    'Дата добавления'
                ])
                df.to_excel(self.file_path, index=False)
                logger.info(f"Создан новый файл Excel: {self.file_path}")
        except Exception as e:
            logger.error(f"Ошибка при создании файла Excel: {e}")
            raise

    def add_warranty_record(self, user_data, product_data, warranty_info):
        """Добавляет запись о новой гарантии в Excel файл"""
        try:
            # Проверяем наличие pandas
            if 'pd' not in globals():
                logger.error("Модуль pandas не импортирован")
                return False

            # Читаем существующий файл
            df = pd.read_excel(self.file_path)

            # Создаем новую запись
            new_record = {
                'Дата активации': warranty_info.get('activation_date'),
                'ID пользователя': user_data.get('telegram_id'),
                'Имя пользователя': user_data.get('user_name'),
                'ID товара': product_data.get('id'),
                'Название товара': product_data.get('name'),
                'Срок гарантии': warranty_info.get('warranty_period'),
                'Дата окончания': warranty_info.get('end_date'),
                'Дата отзыва': warranty_info.get('review_date'),
                'ID скриншота': warranty_info.get('screenshot_id'),
                'Дата добавления': timezone.now().strftime("%d.%m.%Y %H:%M:%S")
            }

            # Добавляем запись в DataFrame
            df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)

            # Сохраняем обновленный файл
            df.to_excel(self.file_path, index=False)
            logger.info(f"Добавлена новая запись о гарантии в Excel для пользователя {user_data.get('user_name')}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении записи в Excel: {e}")
            return False
