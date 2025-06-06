from django.contrib import admin
from .models import User, goods_category, goods, ProductImage, ProductDocument, AdminContact

class UserAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'is_admin', 'is_ai', 'screenshots_count', 'last_screenshot_date')
    search_fields = ('user_name',)
    ordering = ('-telegram_id',)
    fieldsets = (
        (None, {
            'fields': ('telegram_id', 'user_name', 'is_admin', 'is_ai', 'chat_history', 'warranty_data', 'screenshots_count', 'last_screenshot_date', 'messages_count', 'last_message_id')
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

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_primary')

class ProductDocumentInline(admin.TabularInline):
    model = ProductDocument
    extra = 1
    fields = ('document_type', 'pdf_file', 'text_content')

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category')
    list_filter = ('parent_category',)
    search_fields = ('name',)
    inlines = [ProductImageInline, ProductDocumentInline]

class AdminContactAdmin(admin.ModelAdmin):
    list_display = ('admin_contact', 'support_contact', 'is_active', 'updated_at')
    search_fields = ('admin_contact', 'support_contact')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
admin.site.register(AdminContact, AdminContactAdmin)
