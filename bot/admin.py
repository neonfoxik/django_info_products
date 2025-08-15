from django.contrib import admin
from .models import User, goods_category, goods, ProductImage, AdminContact, FAQ
from django import forms

class UserAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'phone_number', 'is_admin', 'is_ai', 'screenshots_count', 'last_screenshot_date')
    search_fields = ('user_name', 'phone_number')
    ordering = ('-telegram_id',)
    fieldsets = (
        (None, {
            'fields': ('telegram_id', 'user_name', 'phone_number', 'is_admin', 'is_ai', 'chat_history', 'warranty_data', 'screenshots_count', 'last_screenshot_date', 'messages_count', 'last_message_id')
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

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'extended_warranty', 'is_active')
    list_filter = ('parent_category', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active', 'extended_warranty')
    inlines = [ProductImageInline, FAQInline]
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

# Регистрируем модели в админ-панели
admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(AdminContact)
