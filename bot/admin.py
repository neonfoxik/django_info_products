from django.contrib import admin
from .models import User, goods_category, goods

class UserAdmin(admin.ModelAdmin):
    list_display = ('user_name',)  # Удалены недопустимые поля
    search_fields = ('user_name',)
    ordering = ('-telegram_id',)  # Изменено на существующее поле

    def get_queryset(self, request):
        """Переопределяем метод для обработки ошибок при получении пользователей."""
        try:
            return super().get_queryset(request)
        except Exception as e:
            return User.objects.none()

class GoodsCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class GoodsAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category')
    list_filter = ('parent_category',)
    search_fields = ('name',)

admin.site.register(User, UserAdmin)
admin.site.register(goods_category, GoodsCategoryAdmin)
admin.site.register(goods, GoodsAdmin)
