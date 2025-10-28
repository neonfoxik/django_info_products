from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class User(models.Model):
    telegram_id = models.CharField(
        primary_key=True,
        max_length=50
    )
    user_name = models.CharField(
        max_length=100,
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
    is_hidden = models.BooleanField(
        default=False,
        verbose_name='Скрыть из бота',
        help_text='Если включено, категория не будет отображаться в боте, но останется в админке'
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
    # Ключ: telegram_id админа (str), значение: список message_id (int) сообщений бота в чате этого админа по данному тикету
    admin_messages = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        verbose_name='ID сообщений бота у админов по тикету',
        help_text='Словарь {admin_telegram_id: [message_id, ...]}'
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
        help_text='Текст, который отображается пользователю при выборе этой категории промокодов. Поддерживает многострочный текст с эмодзи.'
    )
    promocode_template = models.TextField(
        verbose_name='Шаблон текста с промокодом',
        blank=True,
        null=True,
        help_text='Шаблон текста, который будет показан пользователю вместе с промокодом. Используйте {promocode} для вставки промокода. Например: "Ваш промокод: {promocode}"'
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
    
    def save(self, *args, **kwargs):
        """Переопределяем save для правильного сохранения многострочного текста с эмодзи"""
        if self.message_text:
            # Убеждаемся, что переносы строк сохраняются
            self.message_text = self.message_text.replace('\r\n', '\n').replace('\r', '\n')
            # Убеждаемся, что текст правильно кодируется в UTF-8
            if isinstance(self.message_text, str):
                self.message_text = self.message_text.encode('utf-8').decode('utf-8')
        super().save(*args, **kwargs)
    
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


class TypicalIssue(models.Model):
    """Модель для хранения типичных поломок/проблем для товаров"""
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='typical_issues',
        verbose_name='Товар'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Название проблемы',
        help_text='Например: "Не включается", "Нет звука", "Проблемы с WiFi"'
    )
    solution_template = models.TextField(
        verbose_name='Текст решения',
        blank=True,
        null=True,
        help_text='Текст с инструкцией по решению проблемы. Можно оставить пустым, если прикрепляете только файл.'
    )
    solution_file = models.FileField(
        upload_to='typical_solutions/',
        verbose_name='Файл с решением',
        blank=True,
        null=True,
        help_text='PDF, изображение или другой файл с инструкцией. Можно загрузить вместе с текстом или отдельно.'
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
        return f"{self.product.name} - {self.title}"

    class Meta:
        verbose_name = 'Типичная проблема'
        verbose_name_plural = 'Типичные проблемы'
        ordering = ['product', 'order', 'title']


class WarrantyRequest(models.Model):
    """Модель для хранения обращений по гарантии"""
    STATUS_CHOICES = [
        ('selecting_product', 'Выбор товара'),
        ('selecting_issue', 'Выбор проблемы'),
        ('got_solution', 'Получил решение'),
        ('needs_manager', 'Нужен менеджер'),
        ('closed', 'Закрыто'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='warranty_requests',
        verbose_name='Пользователь'
    )
    product = models.ForeignKey(
        'goods',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Товар'
    )
    issue = models.ForeignKey(
        TypicalIssue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Выбранная проблема'
    )
    custom_issue_description = models.TextField(
        null=True,
        blank=True,
        verbose_name='Описание проблемы (если выбрано "Другое")'
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='selecting_product',
        verbose_name='Статус'
    )
    solution_helped = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Решение помогло?'
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
        return f"Обращение #{self.id} от {self.user.user_name}"

    class Meta:
        verbose_name = 'Обращение по гарантии'
        verbose_name_plural = 'Обращения по гарантии'
        ordering = ['-created_at']


class WarrantyAnswer(models.Model):
    """Ответ пользователя на вопрос в рамках конкретного WarrantyRequest"""
    request = models.ForeignKey(
        WarrantyRequest,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Гарантийное обращение'
    )
    question = models.ForeignKey(
        'ProductWarrantyQuestion',
        on_delete=models.CASCADE,
        verbose_name='Вопрос'
    )
    answer_text = models.TextField(
        verbose_name='Ответ пользователя'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    def __str__(self):
        return f"Заявка #{self.request_id} — Q{self.question_id}"

    class Meta:
        verbose_name = 'Ответ на вопрос гарантии'
        verbose_name_plural = 'Ответы на вопросы гарантии'


class SupportAnswer(models.Model):
    """Ответ пользователя на вопрос в рамках конкретного SupportTicket"""
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Обращение в поддержку'
    )
    question = models.ForeignKey(
        'ProductSupportQuestion',
        on_delete=models.CASCADE,
        verbose_name='Вопрос'
    )
    answer_text = models.TextField(
        verbose_name='Ответ пользователя'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    def __str__(self):
        return f"Тикет #{self.ticket_id} — Q{self.question_id}"

    class Meta:
        verbose_name = 'Ответ на вопрос поддержки'
        verbose_name_plural = 'Ответы на вопросы поддержки'


class ProductSupportQuestion(models.Model):
    """Вопросы поддержки, специфичные для конкретного товара"""
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='support_questions',
        verbose_name='Товар'
    )
    text = models.TextField(
        verbose_name='Текст вопроса'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок'
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
        return f"{self.product.name} - Q{self.id}: {self.text[:50]}"

    class Meta:
        verbose_name = 'Вопрос поддержки товара'
        verbose_name_plural = 'Вопросы поддержки товаров'
        ordering = ['product', 'order', 'id']


class ProductWarrantyQuestion(models.Model):
    """Вопросы гарантии, специфичные для конкретного товара"""
    product = models.ForeignKey(
        'goods',
        on_delete=models.CASCADE,
        related_name='warranty_questions',
        verbose_name='Товар'
    )
    text = models.TextField(
        verbose_name='Текст вопроса'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Порядок'
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
        return f"{self.product.name} - Q{self.id}: {self.text[:50]}"

    class Meta:
        verbose_name = 'Вопрос гарантии товара'
        verbose_name_plural = 'Вопросы гарантии товаров'
        ordering = ['product', 'order', 'id']
