from asgiref.sync import async_to_sync
from unittest.mock import AsyncMock

from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from groups.consumers import GroupLocationConsumer
from groups.models import Group, GroupMembership
from users.models import User, UserLocation


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


class GroupApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="creator@example.com",
            password="password123",
            first_name="Creator",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.user).access_token)}"
        )

    def test_group_creator_cannot_exceed_three_active_groups(self):
        for index in range(3):
            group = Group.objects.create(
                name=f"Group {index + 1}",
                created_by=self.user,
                is_active=True,
            )
            GroupMembership.objects.create(group=group, user=self.user)

        response = self.client.post(
            "/api/v1/groups/",
            {"name": "Group 4"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "You can only create up to 3 active groups at a time.",
        )

    def test_group_members_hide_location_until_users_are_connected(self):
        other_user = User.objects.create_user(
            email="friend@example.com",
            password="password123",
            first_name="Friend",
        )
        group = Group.objects.create(name="Trail Team", created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user)
        GroupMembership.objects.create(group=group, user=other_user)
        UserLocation.objects.create(
            user=other_user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.get(f"/api/v1/groups/{group.id}/members/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        friend_member = next(
            member for member in response.data["members"] if member["user_id"] == other_user.id
        )
        self.assertIsNone(friend_member["location"])


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class GroupLocationConsumerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="live@example.com",
            password="password123",
            first_name="Live",
        )
        self.group = Group.objects.create(name="RoamMap Group", created_by=self.user)
        GroupMembership.objects.create(group=self.group, user=self.user)
        self.token = str(RefreshToken.for_user(self.user).access_token)

    def test_websocket_receives_live_stop_and_resume_events(self):
        consumer = GroupLocationConsumer()
        consumer.send_json = AsyncMock()

        live_payload = {
            "group_id": self.group.id,
            "user_id": self.user.id,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "latitude": "27.641100",
            "longitude": "85.482000",
            "accuracy": 5,
            "is_sharing_live": True,
            "stopped_at": None,
            "updated_at": "2026-03-11T10:00:00Z",
        }
        stop_payload = {
            **live_payload,
            "is_sharing_live": False,
            "stopped_at": "2026-03-11T10:01:00Z",
            "updated_at": "2026-03-11T10:01:00Z",
        }
        resume_payload = {
            **live_payload,
            "latitude": "27.642000",
            "longitude": "85.483000",
            "accuracy": 6,
            "is_sharing_live": True,
            "stopped_at": None,
            "updated_at": "2026-03-11T10:02:00Z",
        }

        async_to_sync(consumer.group_location)({"payload": live_payload})
        async_to_sync(consumer.group_location)({"payload": stop_payload})
        async_to_sync(consumer.group_location)({"payload": resume_payload})

        self.assertEqual(consumer.send_json.await_count, 3)
        consumer.send_json.assert_any_await(live_payload)
        consumer.send_json.assert_any_await(stop_payload)
        consumer.send_json.assert_any_await(resume_payload)
