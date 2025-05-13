from django.db import models


class User(models.Model):
    telegram_id = models.CharField(
        primary_key=True,
        max_length=50
    )
    user_name = models.CharField(
        max_length=35,
        verbose_name='Имя',
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
    extended_warranty_products = models.JSONField(
        verbose_name='Товары с расширенной гарантией',
        null=True,
        blank=True,
        default=dict
    )
    def __str__(self):
        return str(self.user_name)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

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
    instructions = models.TextField(
        verbose_name='Инструкция по применению'
    )
    FAQ = models.TextField(
        verbose_name='FAQ'
    )
    warranty = models.TextField(
        verbose_name='Условия гарантия'
    )
    extended_warranty = models.TextField(
        verbose_name='Условия расширенной гарантии',
        default='Для получения расширенной гарантии оставьте отзыв с оценкой 5 звезд на товар.'
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Название товара'
        verbose_name_plural = 'Названия товаров'
