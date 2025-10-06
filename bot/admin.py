from django.contrib import admin
from .models import User, goods_category, goods, ProductImage, Support, FAQ, Instruction, SupportTicket, SupportMessage, OwnerSettings, BroadcastMessage, PromoCode, PromoCodeCategory
from django import forms
from django.db import models


class PromoCodeCategoryForm(forms.ModelForm):
    """Специальная форма для правильного отображения многострочного текста"""
    class Meta:
        model = PromoCodeCategory
        fields = '__all__'
        widgets = {
            'message_text': forms.Textarea(attrs={
                'rows': 15,
                'cols': 100,
                'style': 'width: 100%; font-family: monospace;',
                'class': 'vLargeTextField'
            }),
            'promocode_template': forms.Textarea(attrs={
                'rows': 15,
                'cols': 100,
                'style': 'width: 100%; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;',
                'class': 'vLargeTextField',
                'placeholder': '🎉 Поздравляем!\n\nВаш промокод: {promocode}\n\nИспользуйте его при оформлении заказа.'
            }),
        }
    
    def clean_message_text(self):
        """Очистка и нормализация текста с эмодзи"""
        message_text = self.cleaned_data.get('message_text')
        if message_text:
            # Убеждаемся, что текст правильно кодируется
            message_text = message_text.encode('utf-8').decode('utf-8')
            # Нормализуем переносы строк
            message_text = message_text.replace('\r\n', '\n').replace('\r', '\n')
        return message_text

    def clean_promocode_template(self):
        """Очистка и нормализация шаблона текста с промокодом"""
        template = self.cleaned_data.get('promocode_template')
        if template:
            # Убеждаемся, что текст правильно кодируется
            template = template.encode('utf-8').decode('utf-8')
            # Нормализуем переносы строк
            template = template.replace('\r\n', '\n').replace('\r', '\n')
            # Проверяем наличие маркера {promocode}
            if '{promocode}' not in template:
                from django.core.exceptions import ValidationError
                raise ValidationError('Шаблон должен содержать маркер {promocode} для вставки промокода')
        return template

class UserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'user_name', 'phone_number', 'is_admin', 'is_super_admin', 'is_ozon_admin', 'is_wb_admin', 'is_ai', 'screenshots_count', 'last_screenshot_date')
    search_fields = ('user_name', 'phone_number', 'telegram_id')
    ordering = ('-telegram_id',)
    fieldsets = (
        (None, {
            'fields': (
                'telegram_id', 'user_name', 'phone_number',
                'is_admin', 'is_super_admin', 'is_ozon_admin', 'is_wb_admin',
                'is_ai', 'chat_history', 'warranty_data', 'screenshots_count',
                'last_screenshot_date', 'messages_count', 'last_message_id'
            )
        }),
    )

    def get_queryset(self, request):
        """Переопределяем метод для обработки ошибок при получении пользователей."""
        try:
            return super().get_queryset(request)
        except Exception:
            return self.model.objects.none()

class GoodsCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ('title', 'pdf_file', 'link', 'description', 'order', 'is_active')
    ordering = ('order', 'title')

class FAQAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'order', 'is_active', 'created_at')
    list_filter = ('product', 'is_active', 'created_at')
    search_fields = ('title', 'product__name')
    list_editable = ('order', 'is_active')
    ordering = ('product', 'order', 'title')
    fieldsets = (
        (None, {
            'fields': ('product', 'title', 'pdf_file', 'link', 'description')
        }),
        ('Настройки отображения', {
            'fields': ('order', 'is_active')
        }),
    )

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image',)

class InstructionInline(admin.TabularInline):
    model = Instruction
    extra = 1
    fields = ('title', 'pdf_file', 'order', 'is_active')
    ordering = ('order', 'title')

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'extended_warranty', 'is_active')
    list_filter = ('parent_category', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active', 'extended_warranty')
    inlines = [ProductImageInline, FAQInline, InstructionInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'parent_category', 'is_active')
        }),
        ('Гарантия', {
            'fields': ('extended_warranty',)
        }),
        ('AI поддержка', {
            'fields': ('ai_instruction',),
            'description': 'Инструкция для ИИ при общении с пользователями по данному товару'
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)



class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    fields = ('sender', 'sender_type', 'message_text', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('created_at',)

class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'platform', 'status', 'assigned_admin', 'created_at', 'updated_at')
    list_filter = ('status', 'platform', 'created_at', 'assigned_admin')
    search_fields = ('user__user_name', 'subject')
    list_editable = ('status', 'assigned_admin')
    inlines = [SupportMessageInline]
    readonly_fields = ('created_at', 'updated_at', 'closed_at', 'first_admin_notification_sent', 'second_admin_notification_sent', 'owner_notification_sent')
    fieldsets = (
        (None, {
            'fields': ('user', 'platform', 'subject', 'status', 'assigned_admin')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
        ('Уведомления', {
            'fields': ('first_admin_notification_sent', 'second_admin_notification_sent', 'owner_notification_sent'),
            'classes': ('collapse',)
        }),
    )

class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'sender', 'sender_type', 'message_text_short', 'created_at')
    list_filter = ('sender_type', 'created_at')
    search_fields = ('ticket__id', 'sender__user_name', 'message_text')
    readonly_fields = ('created_at',)
    
    def message_text_short(self, obj):
        return obj.message_text[:50] + '...' if len(obj.message_text) > 50 else obj.message_text
    message_text_short.short_description = 'Сообщение'

class OwnerSettingsAdmin(admin.ModelAdmin):
    list_display = ('owner_telegram_id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('created_at', 'updated_at')

# Регистрируем модели в админ-панели
admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(Support)
admin.site.register(Instruction)
admin.site.register(SupportTicket, SupportTicketAdmin)
admin.site.register(SupportMessage, SupportMessageAdmin)
admin.site.register(OwnerSettings, OwnerSettingsAdmin)


@admin.action(description="Отправить выбранную рассылку всем пользователям")
def send_broadcast(modeladmin, request, queryset):
    from django.utils import timezone
    from bot import bot as telegram_bot
    sent_count_total = 0
    for msg in queryset:
        if msg.is_sent:
            continue
        sent_count = 0
        for u in User.objects.all():
            try:
                telegram_bot.send_message(u.telegram_id, msg.text)
                sent_count += 1
            except Exception:
                continue
        msg.is_sent = True
        msg.sent_at = timezone.now()
        msg.save()
        sent_count_total += sent_count
    modeladmin.message_user(request, f"Отправлено сообщений: {sent_count_total}")


class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "is_sent", "created_at", "sent_at")
    list_filter = ("is_sent", "created_at")
    actions = [send_broadcast]


admin.site.register(BroadcastMessage, BroadcastMessageAdmin)


class PromoCodeInline(admin.TabularInline):
    model = PromoCode
    extra = 1
    fields = ('code', 'is_active', 'is_used')


class PromoCodeCategoryAdmin(admin.ModelAdmin):
    form = PromoCodeCategoryForm
    list_display = ('name', 'instruction_status', 'is_active', 'promocodes_count', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    
    # Настройки для лучшего отображения многострочного текста
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 15, 'cols': 100, 'style': 'width: 100%;'})},
    }
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Специальная настройка для поля message_text
        if 'message_text' in form.base_fields:
            # Используем более универсальный подход
            from django.forms import Textarea
            form.base_fields['message_text'].widget = Textarea(attrs={
                'rows': 15, 
                'cols': 100,
                'style': 'font-family: monospace; width: 100%;',
                'class': 'vLargeTextField'
            })
        return form
    
    def instruction_status(self, obj):
        """Показывает статус инструкции: только файл"""
        has_file = bool(obj.instruction_file)
        
        if has_file:
            return "Файл загружен"
        else:
            return "Нет файла"
    instruction_status.short_description = 'Инструкция'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'is_active')
        }),
        ('Сообщение при выборе категории', {
            'fields': ('message_text',),
            'description': 'Текст, который отображается пользователю при выборе этой категории промокодов. Поддерживает многострочный текст с эмодзи.'
        }),
        ('Шаблон текста с промокодом', {
            'fields': ('promocode_template',),
            'description': 'Шаблон текста, который будет показан пользователю вместе с промокодом. Используйте {promocode} для вставки промокода. Например: "Ваш промокод: {promocode}"'
        }),
        ('Инструкции по применению промокодов', {
            'fields': ('instruction_file',),
            'description': 'Загрузите файл с инструкциями по применению промокодов'
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    inlines = [PromoCodeInline]


class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'category', 'is_used', 'is_active', 'created_at', 'created_by')
    list_filter = ('category', 'is_active', 'is_used', 'created_at')
    search_fields = ('code',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'category', 'is_active', 'is_used')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )


admin.site.register(PromoCode, PromoCodeAdmin)
admin.site.register(PromoCodeCategory, PromoCodeCategoryAdmin)
