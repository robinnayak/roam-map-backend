from django.contrib import admin

from .models import Group, GroupMembership, Waypoint


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'invite_code', 'created_by', 'created_at')
    search_fields = ('name', 'invite_code', 'created_by__email')
    list_filter = ('created_at',)
    list_select_related = ('created_by',)
    readonly_fields = ('created_at',)


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'user', 'joined_at')
    search_fields = ('group__name', 'group__invite_code', 'user__email')
    list_filter = ('joined_at',)
    list_select_related = ('group', 'user')
    readonly_fields = ('joined_at',)


@admin.register(Waypoint)
class WaypointAdmin(admin.ModelAdmin):
    list_display = ('id', 'label', 'group', 'created_by', 'latitude', 'longitude', 'created_at')
    search_fields = ('label', 'group__name', 'created_by__email')
    list_filter = ('created_at',)
    list_select_related = ('group', 'created_by')
    readonly_fields = ('created_at',)
