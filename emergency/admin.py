from django.contrib import admin

from .models import SOSAlert


@admin.register(SOSAlert)
class SOSAlertAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'group',
        'latitude',
        'longitude',
        'is_active',
        'triggered_at',
        'resolved_at',
    )
    search_fields = ('user__email', 'group__name')
    list_filter = ('is_active', 'triggered_at', 'resolved_at')
    list_select_related = ('user', 'group')
