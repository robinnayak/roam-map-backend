from django.contrib import admin

from .models import PackingItem


@admin.register(PackingItem)
class PackingItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'name', 'is_checked', 'sort_order', 'is_default')
    list_filter = ('category', 'is_checked', 'is_default')
    search_fields = ('name', 'category', 'note', 'user__email')
    ordering = ('user__email', 'category', 'sort_order', 'id')

