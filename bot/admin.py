from django.contrib import admin
from .models import User, goods_category, goods, ProductImage, ProductDocument, AdminContact, FAQ
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
    fields = ('title', 'pdf_file', 'description', 'order', 'is_active')
    ordering = ('order', 'title')

class FAQAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'order', 'is_active', 'created_at')
    list_filter = ('product', 'is_active', 'created_at')
    search_fields = ('title', 'product__name')
    list_editable = ('order', 'is_active')
    ordering = ('product', 'order', 'title')
    fieldsets = (
        (None, {
            'fields': ('product', 'title', 'pdf_file', 'description')
        }),
        ('Настройки отображения', {
            'fields': ('order', 'is_active')
        }),
    )

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image',)

class ProductDocumentInline(admin.TabularInline):
    model = ProductDocument
    extra = 1
    fields = ('document_type', 'pdf_file', 'text_content')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        def clean(self):
            cleaned_data = super(formset, self).clean()
            if not cleaned_data:
                return cleaned_data
                
            # Получаем все документы текущего товара
            if obj:
                existing_docs = ProductDocument.objects.filter(product=obj)
                doc_types = existing_docs.values_list('document_type', flat=True)
                
                # Проверяем каждый документ в форме
                for form in self.forms:
                    if form.is_valid() and not form.cleaned_data.get('DELETE', False):
                        doc_type = form.cleaned_data.get('document_type')
                        if doc_type in doc_types:
                            form.add_error('document_type', 'Документ этого типа уже существует для данного товара')
                            raise forms.ValidationError('Документ этого типа уже существует для данного товара')
            return cleaned_data
            
        formset.clean = clean
        return formset

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'extended_warranty', 'is_active')
    list_filter = ('parent_category', 'is_active')
    search_fields = ('name',)
    list_editable = ('is_active', 'extended_warranty')
    inlines = [ProductImageInline, ProductDocumentInline, FAQInline]
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

class AdminContactAdmin(admin.ModelAdmin):
    list_display = ('admin_contact', 'support_contact', 'is_active', 'updated_at')
    search_fields = ('admin_contact', 'support_contact')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
admin.site.register(AdminContact, AdminContactAdmin)
admin.site.register(FAQ, FAQAdmin)
