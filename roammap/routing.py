from django.urls import path

from chat.consumers import DirectMessageConsumer
from groups.consumers import GroupLocationConsumer


websocket_urlpatterns = [
    path("ws/groups/<int:group_id>/", GroupLocationConsumer.as_asgi()),
    path("ws/dm/<int:user_id>/", DirectMessageConsumer.as_asgi()),
]
