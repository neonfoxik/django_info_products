from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class User(models.Model):
    telegram_id = models.CharField(
        primary_key=True,
        max_length=50,
        db_index=True
    )
    user_name = models.CharField(
        max_length=35,
        verbose_name='Имя',
        db_index=True
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Является ли администратором',
        db_index=True
    )
    is_ai = models.BooleanField(
        default=False,
        verbose_name='Используется ли AI',
        db_index=True
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
        verbose_name='Количество отправленных скриншотов за день',
        validators=[MinValueValidator(0)]
    )
    last_screenshot_date = models.DateField(
        default=timezone.now,
        verbose_name='Дата последней отправки скриншота',
        db_index=True
    )
    messages_count = models.IntegerField(
        default=0,
        verbose_name='Количество сообщений в текущем действии',
        validators=[MinValueValidator(0)]
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
        ordering = ['-telegram_id']
        indexes = [
            models.Index(fields=['user_name']),
            models.Index(fields=['is_admin']),
            models.Index(fields=['is_ai']),
        ]


class goods_category(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='Название категории',
        unique=True,
        db_index=True
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Категория товаров'
        verbose_name_plural = 'Категории товаров'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]


class goods(models.Model):
    parent_category = models.ForeignKey(
        goods_category,
        on_delete=models.CASCADE,
        verbose_name='Родительская категория',
        related_name='goods'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Название товара',
        db_index=True
    )
    image = models.ImageField(
        upload_to='products/',
        verbose_name='Изображение товара',
        null=True,
        blank=True
    )
    instructions = models.TextField(
        verbose_name='Инструкция по применению'
    )
    FAQ = models.TextField(
        verbose_name='FAQ'
    )
    warranty = models.TextField(
        verbose_name='Условия гарантия'
    )
    extended_warranty = models.FloatField(
        verbose_name='Срок расширенной гарантии (в годах)',
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(10.0)]
    )
    is_returned = models.BooleanField(
        default=False,
        verbose_name='Товар возвращен',
        db_index=True
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_returned']),
            models.Index(fields=['parent_category']),
        ]
