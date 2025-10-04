from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


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
    is_super_admin = models.BooleanField(
        default=False,
        verbose_name='Главный админ'
    )
    is_ozon_admin = models.BooleanField(
        default=False,
        verbose_name='Админ Озон'
    )
    is_wb_admin = models.BooleanField(
        default=False,
        verbose_name='Админ ВБ'
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
    received_promocode = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='Полученный промокод',
        help_text='Промокод, который получил пользователь'
    )
    received_promocodes_by_category = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name='Полученные промокоды по категориям',
        help_text='Словарь с полученными промокодами по категориям: {category_id: promocode}'
    )

    # Ключ: ticket_id (str), значение: список ID сообщений с файлами, уже отправленных администратору
    received_ticket_files = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name='Отправленные файлы тикетов администратору',
        help_text='Какие файлы (ID сообщений) по каждому тикету уже были отправлены этому администратору'
    )

    def __str__(self):
        return str(self.user_name)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

class Support(models.Model):
    admin_ozon = models.CharField(
        max_length=255,
        verbose_name='Админ Озон',
        default='Для связи с администратором Озон напишите на email: ozon@example.com'
    )
    admin_wildberries = models.CharField(
        max_length=255,
        verbose_name='Админ Вайлдберриз',
        default='Для связи с администратором Вайлдберриз напишите на email: wildberries@example.com'
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
        return f"Контакты поддержки (обновлены: {self.updated_at.strftime('%d.%m.%Y %H:%M')})"

    class Meta:
        verbose_name = 'Контакты поддержки'
        verbose_name_plural = 'Контакты поддержки'
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
        verbose_name='Название FAQ',
        help_text='Введите название FAQ.'
    )
    pdf_file = models.FileField(
        upload_to='faq/',
        verbose_name='PDF файл FAQ',
        blank=True,
        null=True,
        help_text='Загрузите PDF файл (необязательно).'
    )
    link = models.URLField(
        max_length=500,
        verbose_name='Ссылка',
        blank=True,
        null=True,
        help_text='Ссылка для кнопки (необязательно).'
    )
    description = models.TextField(
        verbose_name='Описание',
        blank=True,
        null=True,
        help_text='Дополнительное описание FAQ (необязательно).'
    )
    order = models.PositiveIntegerField(
        verbose_name='Порядок отображения',
        default=0,
        help_text='Чем меньше число, тем выше в списке.'
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
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    def __str__(self):
        return f"Изображение {self.product.name}"

    class Meta:
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'
        ordering = ['-created_at']

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
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Название товара'
        verbose_name_plural = 'Названия товаров'

    @property
    def primary_image(self):
        return self.images.first()

    @property
    def is_returned(self):
        return False

class Instruction(models.Model):
    """Модель для хранения инструкций к товарам"""
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='instructions',
        verbose_name='Товар'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название инструкции',
        help_text='Введите название инструкции.'
    )
    pdf_file = models.FileField(
        upload_to='instructions/',
        verbose_name='PDF файл инструкции',
        help_text='Загрузите PDF файл инструкции.'
    )
    order = models.PositiveIntegerField(
        verbose_name='Порядок отображения',
        default=0,
        help_text='Чем меньше число, тем выше в списке.'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
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
        verbose_name = 'Инструкция'
        verbose_name_plural = 'Инструкции'
        ordering = ['product', 'order', 'title']


class SupportTicket(models.Model):
    """Модель для хранения обращений в службу поддержки"""
    STATUS_CHOICES = [
        ('open', 'Открыто'),
        ('in_progress', 'В обработке'),
        ('closed', 'Закрыто'),
    ]
    
    PLATFORM_CHOICES = [
        ('ozon', 'Озон'),
        ('wildberries', 'Вайлдберриз'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets',
        verbose_name='Пользователь'
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        verbose_name='Платформа',
        help_text='Платформа, по которой было создано обращение'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Статус'
    )
    assigned_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name='Назначенный администратор',
        limit_choices_to={'is_admin': True}
    )
    subject = models.CharField(
        max_length=255,
        verbose_name='Тема обращения',
        default='Обращение в службу поддержки'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата закрытия'
    )
    first_admin_notification_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время отправки первого уведомления админам'
    )
    second_admin_notification_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время отправки второго уведомления админам'
    )
    owner_notification_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время отправки уведомления владельцу'
    )
    unread_by_admin = models.BooleanField(
        default=False,
        verbose_name='Есть непрочитанные сообщения для админа'
    )
    unread_by_user = models.BooleanField(
        default=False,
        verbose_name='Есть непрочитанные сообщения для пользователя'
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время последнего сообщения'
    )
    last_message_from = models.CharField(
        max_length=10,
        choices=[('user','Пользователь'),('admin','Администратор')],
        null=True,
        blank=True,
        verbose_name='Последнее сообщение от'
    )
    messages_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество сообщений'
    )

    def __str__(self):
        return f"Обращение #{self.id} от {self.user.user_name} ({self.get_platform_display()})"

    class Meta:
        verbose_name = 'Обращение в поддержку'
        verbose_name_plural = 'Обращения в поддержку'
        ordering = ['-created_at']


class SupportMessage(models.Model):
    """Модель для хранения сообщений в обращениях поддержки"""
    SENDER_CHOICES = [
        ('user', 'Пользователь'),
        ('admin', 'Администратор'),
    ]
    
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Обращение'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Отправитель'
    )
    sender_type = models.CharField(
        max_length=10,
        choices=SENDER_CHOICES,
        verbose_name='Тип отправителя'
    )
    message_text = models.TextField(
        verbose_name='Текст сообщения'
    )
    telegram_message_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='ID сообщения в Telegram'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата отправки'
    )
    # New fields for media support
    content_type = models.CharField(
        max_length=20,
        default='text',
        verbose_name='Тип контента (text/photo/video/document)'
    )
    file_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='File ID медиаконтента'
    )
    caption = models.TextField(
        null=True,
        blank=True,
        verbose_name='Подпись к медиа'
    )

    def __str__(self):
        return f"Сообщение от {self.sender.user_name} в обращении #{self.ticket.id}"

    class Meta:
        verbose_name = 'Сообщение поддержки'
        verbose_name_plural = 'Сообщения поддержки'
        ordering = ['created_at']


class OwnerSettings(models.Model):
    """Модель для хранения настроек владельца (для уведомлений)"""
    owner_telegram_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Telegram ID владельца'
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
        return f"Настройки владельца {self.owner_telegram_id}"

    class Meta:
        verbose_name = 'Настройки владельца'
        verbose_name_plural = 'Настройки владельца'


class BroadcastMessage(models.Model):
    """Модель для хранения и отправки рассылок пользователям"""
    title = models.CharField(
        max_length=255,
        verbose_name='Заголовок'
    )
    text = models.TextField(
        verbose_name='Текст сообщения'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name='Отправлено'
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время отправки'
    )

    def __str__(self):
        return f"{self.title} ({'отправлено' if self.is_sent else 'не отправлено'})"

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'


class PromoCodeCategory(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название категории'
    )
    message_text = models.TextField(
        verbose_name='Текст сообщения при выборе категории',
        blank=True,
        null=True,
        help_text='Текст, который отображается пользователю при выборе этой категории промокодов'
    )
    instruction_file = models.FileField(
        upload_to='instructions/promocodes/',
        verbose_name='Файл инструкции',
        blank=True,
        null=True,
        help_text='PDF или другой файл с инструкциями по применению промокодов'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    def __str__(self):
        return self.name
    
    def promocodes_count(self):
        """Количество активных неиспользованных промокодов в категории"""
        return self.promocodes.filter(is_active=True, is_used=False).count()
    promocodes_count.short_description = 'Кол-во промокодов'
    
    class Meta:
        verbose_name = 'Категория промокодов'
        verbose_name_plural = 'Категории промокодов'
        ordering = ['name']


class PromoCode(models.Model):
    """Модель для хранения промокодов"""
    category = models.ForeignKey(
        PromoCodeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promocodes',
        verbose_name='Категория'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Промокод',
        help_text='Уникальный код промокода'
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='Использован',
        help_text='Был ли промокод использован'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Активен ли промокод'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создан администратором',
        help_text='Администратор, который создал промокод'
    )

    def __str__(self):
        return f"{self.code} ({'использован' if self.is_used else 'активен' if self.is_active else 'неактивен'})"

    def can_be_used(self):
        """Проверяет, можно ли использовать промокод"""
        return self.is_active and not self.is_used

    def use(self):
        """Использует промокод (помечает как использованный)"""
        if self.can_be_used():
            self.is_used = True
            self.save()
            return True
        return False

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'
        ordering = ['-created_at']
