from django.urls import path

from groups.consumers import GroupLocationConsumer


websocket_urlpatterns = [
    path("ws/groups/<int:group_id>/", GroupLocationConsumer.as_asgi()),
]
