from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer

from .models import Conversation, DirectMessage, users_have_accepted_connection
from .serializers import DirectMessageSerializer


def get_dm_room_name(conversation_id):
    return f'dm_{conversation_id}'


def broadcast_direct_message(conversation_id, message_payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        get_dm_room_name(conversation_id),
        {
            'type': 'direct_message_event',
            'payload': {
                'type': 'direct.message',
                'message': message_payload,
            },
        },
    )


class DirectMessageConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.other_user_id = self.scope['url_route']['kwargs']['user_id']
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        if user.id == self.other_user_id:
            await self.close(code=4403)
            return

        has_connection = await self._users_have_connection(user.id, self.other_user_id)
        if not has_connection:
            await self.close(code=4403)
            return

        self.conversation_id = await self._get_or_create_conversation_id(user.id, self.other_user_id)
        self.room_group_name = get_dm_room_name(self.conversation_id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            return

        body = (content.get('body') or '').strip()
        if not body:
            await self.send_json(
                {
                    'type': 'direct.message.error',
                    'detail': 'Message body cannot be empty.',
                }
            )
            return

        if not await self._users_have_connection(user.id, self.other_user_id):
            await self.close(code=4403)
            return

        message_payload = await self._create_message(user.id, self.other_user_id, body)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'direct_message_event',
                'payload': {
                    'type': 'direct.message',
                    'message': message_payload,
                },
            },
        )

    async def direct_message_event(self, event):
        await self.send_json(event['payload'])

    @database_sync_to_async
    def _users_have_connection(self, user_id, other_user_id):
        return users_have_accepted_connection(user_id, other_user_id)

    @database_sync_to_async
    def _get_or_create_conversation_id(self, user_id, other_user_id):
        conversation, _ = Conversation.get_or_create_for_user_ids(user_id, other_user_id)
        return conversation.id

    @database_sync_to_async
    def _create_message(self, sender_id, recipient_id, body):
        sender = self.scope['user'].__class__.objects.get(id=sender_id)
        recipient = self.scope['user'].__class__.objects.get(id=recipient_id)
        conversation, _ = Conversation.get_or_create_for_user_ids(sender_id, recipient_id)
        message = DirectMessage.objects.create(
            conversation=conversation,
            sender=sender,
            recipient=recipient,
            body=body,
        )
        conversation.save(update_fields=['updated_at'])
        return DirectMessageSerializer(message).data
