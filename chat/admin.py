from django.contrib import admin

from .models import Conversation, DirectMessage


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_one', 'user_two', 'created_at', 'updated_at')
    search_fields = ('user_one__email', 'user_two__email')
    list_select_related = ('user_one', 'user_two')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'recipient', 'created_at', 'is_read')
    search_fields = ('sender__email', 'recipient__email', 'body')
    list_filter = ('is_read', 'created_at')
    list_select_related = ('conversation', 'sender', 'recipient')
    readonly_fields = ('created_at',)

