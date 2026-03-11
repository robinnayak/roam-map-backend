from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from groups.models import GroupMembership


class GroupLocationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"group_{self.group_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        is_member = await self._is_group_member(user.id, self.group_id)
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return

        payload = {
            "type": "group.location",
            "group_id": self.group_id,
            "user_id": user.id,
            "latitude": content.get("latitude"),
            "longitude": content.get("longitude"),
            "accuracy": content.get("accuracy"),
            "is_sharing_live": content.get("is_sharing_live", True),
            "stopped_at": content.get("stopped_at"),
            "updated_at": content.get("updated_at"),
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "group_location",
                "payload": payload,
            },
        )

    async def group_location(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def _is_group_member(self, user_id, group_id):
        return GroupMembership.objects.filter(group_id=group_id, user_id=user_id).exists()
