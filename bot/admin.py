from django.contrib import admin
from .models import User, goods_category, goods

class UserAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'telegram_id', 'is_admin', 'is_ai', 'screenshots_count', 'last_screenshot_date')
    list_filter = ('is_admin', 'is_ai')
    search_fields = ('user_name', 'telegram_id')
    readonly_fields = ('telegram_id', 'chat_history', 'warranty_data')
    ordering = ('-telegram_id',)

    def get_queryset(self, request):
        """Переопределяем метод для обработки ошибок при получении пользователей."""
        try:
            return super().get_queryset(request)
        except Exception as e:
            return User.objects.none()

class GoodsCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'is_returned', 'extended_warranty')
    list_filter = ('parent_category', 'is_returned')
    search_fields = ('name', 'instructions', 'FAQ', 'warranty')
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'parent_category', 'image')
        }),
        ('Описание', {
            'fields': ('instructions', 'FAQ', 'warranty')
        }),
        ('Гарантия', {
            'fields': ('extended_warranty', 'is_returned')
        }),
    )

admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
