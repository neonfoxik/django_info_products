from django.contrib import admin
from .models import User, goods_category, goods, ProductImage, Support, FAQ, Instruction, SupportTicket, SupportMessage, OwnerSettings, BroadcastMessage, PromoCode, PromoCodeCategory, TypicalIssue, WarrantyRequest, WarrantyAnswer, SupportAnswer, ProductWarrantyQuestion, ProductSupportQuestion
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

# Перемещаем класс GoodsAdmin в конец файла, после всех необходимых классов



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
    actions = ["force_close_tickets"]

    def _cleanup_admin_messages(self, ticket):
        try:
            from bot import bot as telegram_bot
            mapping = ticket.admin_messages or {}
            for admin_chat_id_str, ids in mapping.items():
                try:
                    admin_chat_id = int(admin_chat_id_str)
                except Exception:
                    continue
                for mid in ids or []:
                    try:
                        telegram_bot.delete_message(admin_chat_id, int(mid))
                    except Exception:
                        continue
            ticket.admin_messages = {}
            ticket.save(update_fields=['admin_messages'])
        except Exception:
            pass

    @admin.action(description="Принудительно закрыть выбранные обращения (только суперпользователь)")
    def force_close_tickets(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Недостаточно прав: требуется суперпользователь.", level=admin.messages.ERROR)
            return
        from django.utils import timezone as dj_tz
        closed = 0
        for ticket in queryset:
            try:
                if ticket.status != 'closed':
                    ticket.status = 'closed'
                    ticket.closed_at = dj_tz.now()
                    ticket.save(update_fields=['status', 'closed_at'])
                    # очистка сообщений у админов
                    self._cleanup_admin_messages(ticket)
                    closed += 1
            except Exception:
                continue
        self.message_user(request, f"Закрыто обращений: {closed}")

    def save_model(self, request, obj, form, change):
        # Если суперпользователь переводит обращение в закрытое — выполним принудительную очистку
        if change and 'status' in form.changed_data:
            try:
                prev = type(obj).objects.get(pk=obj.pk)
            except type(obj).DoesNotExist:
                prev = None
            super().save_model(request, obj, form, change)
            try:
                if request.user.is_superuser and obj.status == 'closed' and (not prev or prev.status != 'closed'):
                    self._cleanup_admin_messages(obj)
            except Exception:
                pass
            return
        super().save_model(request, obj, form, change)

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
# Перемещаем регистрацию GoodsAdmin в конец файла


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


class TypicalIssueInline(admin.TabularInline):
    model = TypicalIssue
    extra = 1
    fields = ('title', 'order', 'is_active')
    ordering = ('order', 'title')


class TypicalIssueForm(forms.ModelForm):
    """Специальная форма для правильного отображения текстовых полей"""
    class Meta:
        model = TypicalIssue
        fields = '__all__'
        widgets = {
            'solution_template': forms.Textarea(attrs={
                'rows': 15,
                'cols': 100,
                'style': 'width: 100%; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;',
                'class': 'vLargeTextField',
                'placeholder': '1. Проверьте подключение кабеля питания\n2. Нажмите и удерживайте кнопку включения 5 секунд\n3. Если не помогло, выполните сброс настроек:\n   - Нажмите кнопку Reset\n   - Дождитесь перезагрузки'
            }),
        }

    def clean_solution_template(self):
        """Очистка и нормализация текста решения"""
        template = self.cleaned_data.get('solution_template')
        if template:
            # Убеждаемся, что текст правильно кодируется и поддерживает эмодзи
            try:
                template = template.encode('utf-8').decode('utf-8')
            except UnicodeError:
                # Если есть проблемы с кодировкой, пытаемся исправить
                template = template.encode('utf-8', errors='ignore').decode('utf-8')
            
            # Нормализуем переносы строк
            template = template.replace('\r\n', '\n').replace('\r', '\n')
            
            # Убираем лишние пробелы в начале и конце строк
            lines = template.split('\n')
            cleaned_lines = [line.rstrip() for line in lines]
            template = '\n'.join(cleaned_lines)
            
        return template


class TypicalIssueProductInline(admin.StackedInline):
    model = TypicalIssue
    extra = 1
    fields = ('title', 'solution_template', 'solution_file', 'order', 'is_active')
    ordering = ('order', 'title')
    verbose_name = 'Типичная проблема'
    verbose_name_plural = 'Типичные проблемы'
    form = TypicalIssueForm


class ProductWarrantyQuestionInline(admin.StackedInline):
    model = ProductWarrantyQuestion
    extra = 1
    fields = ('text', 'order', 'is_active')
    ordering = ('order',)
    verbose_name = 'Вопрос гарантии'
    verbose_name_plural = 'Вопросы гарантии'


class ProductSupportQuestionInline(admin.StackedInline):
    model = ProductSupportQuestion
    extra = 1
    fields = ('text', 'order', 'is_active')
    ordering = ('order',)
    verbose_name = 'Вопрос поддержки'
    verbose_name_plural = 'Вопросы поддержки'


class TypicalIssueAdmin(admin.ModelAdmin):
    form = TypicalIssueForm
    list_display = ('title', 'product', 'order', 'is_active', 'created_at')
    list_filter = ('product', 'is_active', 'created_at')
    search_fields = ('title', 'product__name')
    list_editable = ('order', 'is_active')
    ordering = ('product', 'order', 'title')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('product', 'title', 'is_active')
        }),
        ('Решение проблемы', {
            'fields': ('solution_template', 'solution_file'),
            'description': 'Вы можете добавить текстовую инструкцию, файл или и то, и другое. При отправке пользователю будет показан текст, а затем отправлен файл (если прикреплен).'
        }),
        ('Настройки отображения', {
            'fields': ('order',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')


class WarrantyRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'issue', 'status', 'solution_helped', 'created_at')
    list_filter = ('status', 'solution_helped', 'product', 'created_at')
    search_fields = ('user__user_name', 'product__name', 'issue__title')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'product', 'issue', 'status')
        }),
        ('Детали обращения', {
            'fields': ('custom_issue_description', 'solution_helped')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


admin.site.register(TypicalIssue, TypicalIssueAdmin)
admin.site.register(WarrantyRequest, WarrantyRequestAdmin)


class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'extended_warranty', 'is_active')
    list_filter = ('parent_category', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active', 'extended_warranty')
    inlines = [ProductImageInline, FAQInline, InstructionInline, TypicalIssueProductInline, ProductWarrantyQuestionInline, ProductSupportQuestionInline]
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


# Регистрируем все модели в админ-панели
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(Support)
admin.site.register(Instruction)
admin.site.register(SupportTicket, SupportTicketAdmin)
admin.site.register(SupportMessage, SupportMessageAdmin)
admin.site.register(OwnerSettings, OwnerSettingsAdmin)

@admin.register(ProductWarrantyQuestion)
class ProductWarrantyQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "order", "is_active", "text", "created_at", "updated_at")
    list_filter = ("product", "is_active")
    search_fields = ("text", "product__name")
    ordering = ("product", "order", "id")

@admin.register(WarrantyAnswer)
class WarrantyAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "question", "created_at")
    search_fields = ("answer_text",)
    autocomplete_fields = ("request", "question")

@admin.register(ProductSupportQuestion)
class ProductSupportQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "order", "is_active", "text", "created_at", "updated_at")
    list_filter = ("product", "is_active")
    search_fields = ("text", "product__name")
    ordering = ("product", "order", "id")

@admin.register(SupportAnswer)
class SupportAnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "question", "created_at")
    search_fields = ("answer_text",)
    autocomplete_fields = ("ticket", "question")
