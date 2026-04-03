from django.urls import path

from .views import ConversationHistoryView, MarkConversationReadView, SendDirectMessageView

urlpatterns = [
    path('<int:user_id>/', ConversationHistoryView.as_view(), name='message-history'),
    path('<int:user_id>/send/', SendDirectMessageView.as_view(), name='message-send'),
    path('<int:user_id>/read/', MarkConversationReadView.as_view(), name='message-read'),
]

