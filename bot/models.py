from django.db import models
from django.utils import timezone


class User(models.Model):
    telegram_id = models.CharField(
        primary_key=True,
        max_length=50
    )
    user_name = models.CharField(
        max_length=35,
        verbose_name='Имя',
    )
    phone_number = models.CharField(
        max_length=20,
        verbose_name='Номер телефона',
        null=True,
        blank=True
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Является ли администратором'
    )
    is_ai = models.BooleanField(
        default=False,
        verbose_name='Используется ли AI'
    )
    chat_history = models.JSONField(
        verbose_name='История переписки пользователя',
        null=True,
        blank=True,
        default=dict
    )
    warranty_data = models.JSONField(
        verbose_name='Данные о гарантиях и скриншотах',
        null=True,
        blank=True,
        default=dict
    )
    screenshots_count = models.IntegerField(
        default=0,
        verbose_name='Количество отправленных скриншотов за день'
    )
    last_screenshot_date = models.DateField(
        default=timezone.now,
        verbose_name='Дата последней отправки скриншота'
    )
    messages_count = models.IntegerField(
        default=0,
        verbose_name='Количество сообщений в текущем действии'
    )
    last_message_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='ID последнего сообщения'
    )

    def __str__(self):
        return str(self.user_name)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

class AdminContact(models.Model):
    admin_contact = models.CharField(
        max_length=255,
        verbose_name='Контакт администратора',
        default='Для связи с администратором напишите на email: admin@example.com'
    )
    support_contact = models.CharField(
        max_length=255,
        verbose_name='Контакт поддержки',
        default='Для связи с поддержкой напишите на email: support@example.com'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    def __str__(self):
        return f"Контакты администратора (обновлены: {self.updated_at.strftime('%d.%m.%Y %H:%M')})"

    class Meta:
        verbose_name = 'Контакт администратора'
        verbose_name_plural = 'Контакты администраторов'
        ordering = ['-updated_at']

class goods_category(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='Название категории'
    )
    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Категория товаров'
        verbose_name_plural = 'Категории товаров'

class FAQ(models.Model):
    """Модель для хранения отдельных FAQ"""
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='faq_items',
        verbose_name='Товар'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название FAQ'
    )
    pdf_file = models.FileField(
        upload_to='faq/',
        verbose_name='PDF файл FAQ'
    )
    description = models.TextField(
        verbose_name='Описание',
        blank=True,
        null=True
    )
    order = models.PositiveIntegerField(
        verbose_name='Порядок отображения',
        default=0
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    def __str__(self):
        return f"{self.title} - {self.product.name}"

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
        ordering = ['product', 'order', 'title']

class ProductImage(models.Model):
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Товар'
    )
    image = models.ImageField(
        upload_to='products/images/',
        verbose_name='Изображение товара'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Основное изображение'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    def __str__(self):
        return f"Изображение {self.product.name}"

    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'
        ordering = ['-is_primary', '-created_at']

class ProductDocument(models.Model):
    DOCUMENT_TYPES = [
        ('instructions', 'Инструкция'),
        ('warranty', 'Гарантия'),
        ('faq', 'FAQ'),
    ]

    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Товар'
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        verbose_name='Тип документа'
    )
    pdf_file = models.FileField(
        upload_to='products/documents/',
        verbose_name='PDF документ',
        null=True,
        blank=True
    )
    text_content = models.TextField(
        verbose_name='Текстовое содержимое',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    def __str__(self):
        return f"{self.get_document_type_display()} для {self.product.name}"

    class Meta:
        verbose_name = 'Документ товара'
        verbose_name_plural = 'Документы товаров'
        ordering = ['-created_at']
        unique_together = ['product', 'document_type']

class goods(models.Model):
    parent_category = models.ForeignKey(
        goods_category,
        on_delete=models.CASCADE,
        verbose_name='Родительская категория'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название товара'
    )
    extended_warranty = models.FloatField(
        verbose_name='Срок расширенной гарантии (в годах)',
        default=1.0
    )
    ai_instruction = models.TextField(
        verbose_name='Инструкция для ИИ поддержки',
        blank=True,
        null=True,
        help_text='Системное сообщение для ИИ при общении по данному товару'
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Название товара'
        verbose_name_plural = 'Названия товаров'

    @property
    def instructions(self):
        doc = self.documents.filter(document_type='instructions').first()
        return doc.text_content if doc else None

    @property
    def warranty(self):
        doc = self.documents.filter(document_type='warranty').first()
        return doc.text_content if doc else None

    @property
    def FAQ(self):
        doc = self.documents.filter(document_type='faq').first()
        return doc.text_content if doc else None

    @property
    def primary_image(self):
        return self.images.filter(is_primary=True).first()

    @property
    def is_returned(self):
        return False
