from asgiref.sync import async_to_sync
from unittest.mock import AsyncMock

from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from chat.consumers import DirectMessageConsumer
from chat.models import Conversation, DirectMessage
from users.models import User, UserConnection

TEST_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}


class DirectMessageApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='alice@example.com',
            password='password123',
            first_name='Alice',
        )
        self.other_user = User.objects.create_user(
            email='bob@example.com',
            password='password123',
            first_name='Bob',
        )
        self.third_user = User.objects.create_user(
            email='carol@example.com',
            password='password123',
            first_name='Carol',
        )
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=UserConnection.Status.ACCEPTED,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(self.user).access_token)}'
        )

    def test_send_message_creates_conversation_once_per_pair(self):
        first_response = self.client.post(
            f'/api/v1/messages/{self.other_user.id}/send/',
            {'body': 'Hello Bob'},
            format='json',
        )
        second_response = self.client.post(
            f'/api/v1/messages/{self.other_user.id}/send/',
            {'body': 'Second hello'},
            format='json',
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(DirectMessage.objects.count(), 2)

    def test_send_message_returns_403_when_users_are_not_connected(self):
        response = self.client.post(
            f'/api/v1/messages/{self.third_user.id}/send/',
            {'body': 'Hello stranger'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data['detail'],
            'Direct messages are only available for accepted connections.',
        )

    def test_history_returns_messages_oldest_to_newest(self):
        conversation = Conversation.get_or_create_for_users(self.user, self.other_user)[0]
        DirectMessage.objects.create(
            conversation=conversation,
            sender=self.user,
            recipient=self.other_user,
            body='First',
        )
        DirectMessage.objects.create(
            conversation=conversation,
            sender=self.other_user,
            recipient=self.user,
            body='Second',
        )

        response = self.client.get(f'/api/v1/messages/{self.other_user.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['body'] for item in response.data['results']], ['First', 'Second'])
        self.assertEqual(response.data['conversation_id'], conversation.id)

    def test_mark_read_marks_only_incoming_unread_messages(self):
        conversation = Conversation.get_or_create_for_users(self.user, self.other_user)[0]
        incoming_one = DirectMessage.objects.create(
            conversation=conversation,
            sender=self.other_user,
            recipient=self.user,
            body='First unread',
        )
        incoming_two = DirectMessage.objects.create(
            conversation=conversation,
            sender=self.other_user,
            recipient=self.user,
            body='Second unread',
        )
        outgoing = DirectMessage.objects.create(
            conversation=conversation,
            sender=self.user,
            recipient=self.other_user,
            body='Outgoing',
        )

        response = self.client.post(f'/api/v1/messages/{self.other_user.id}/read/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['marked_read'], 2)
        incoming_one.refresh_from_db()
        incoming_two.refresh_from_db()
        outgoing.refresh_from_db()
        self.assertTrue(incoming_one.is_read)
        self.assertTrue(incoming_two.is_read)
        self.assertFalse(outgoing.is_read)


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class DirectMessageConsumerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='ws-alice@example.com',
            password='password123',
            first_name='Alice',
        )
        self.other_user = User.objects.create_user(
            email='ws-bob@example.com',
            password='password123',
            first_name='Bob',
        )
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=UserConnection.Status.ACCEPTED,
        )

    def test_direct_message_event_sends_envelope(self):
        consumer = DirectMessageConsumer()
        consumer.send_json = AsyncMock()

        payload = {
            'type': 'direct.message',
            'message': {
                'id': 1,
                'conversation': 1,
                'sender': {'id': self.user.id, 'email': self.user.email, 'first_name': 'Alice', 'last_name': ''},
                'recipient': {'id': self.other_user.id, 'email': self.other_user.email, 'first_name': 'Bob', 'last_name': ''},
                'body': 'Hello from socket',
                'created_at': '2026-04-02T12:00:00Z',
                'is_read': False,
            },
        }

        async_to_sync(consumer.direct_message_event)({'payload': payload})

        consumer.send_json.assert_awaited_once_with(payload)

    def test_receive_json_persists_message_for_connected_users(self):
        consumer = DirectMessageConsumer()
        consumer.scope = {'user': self.user}
        consumer.other_user_id = self.other_user.id
        consumer.room_group_name = 'dm_test'
        consumer.channel_layer = type(
            'Layer',
            (),
            {'group_send': AsyncMock()},
        )()
        consumer.send_json = AsyncMock()

        async_to_sync(consumer.receive_json)({'body': 'Socket hello'})

        self.assertEqual(DirectMessage.objects.count(), 1)
        message = DirectMessage.objects.get()
        self.assertEqual(message.body, 'Socket hello')
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.recipient, self.other_user)
        consumer.channel_layer.group_send.assert_awaited()

