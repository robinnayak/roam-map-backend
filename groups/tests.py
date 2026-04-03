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

    def test_group_creation_creates_owner_membership(self):
        response = self.client.post(
            "/api/v1/groups/",
            {"name": "Owner Trip"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = GroupMembership.objects.get(
            group_id=response.data["id"],
            user=self.user,
        )
        self.assertEqual(membership.role, "owner")
        self.assertEqual(response.data["user_role"], "owner")
        self.assertEqual(response.data["member_count"], 1)

    def test_group_creator_cannot_exceed_three_active_groups(self):
        for index in range(3):
            group = Group.objects.create(
                name=f"Group {index + 1}",
                created_by=self.user,
                is_active=True,
            )
            GroupMembership.objects.create(group=group, user=self.user, role="owner")

        response = self.client.post(
            "/api/v1/groups/",
            {"name": "Group 4"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "You already created 3 active trips. Delete one to create a new trip.",
        )

    def test_group_list_includes_groups_created_by_user_even_if_membership_is_missing(self):
        group = Group.objects.create(name="Broken Owner Trip", created_by=self.user)

        response = self.client.get("/api/v1/groups/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["groups"]), 1)
        self.assertEqual(response.data["groups"][0]["id"], group.id)
        self.assertEqual(response.data["groups"][0]["user_role"], "owner")
        self.assertTrue(
            GroupMembership.objects.filter(group=group, user=self.user, role="owner").exists()
        )

    def test_group_list_includes_joined_groups_for_member(self):
        owner = User.objects.create_user(
            email="owner@example.com",
            password="password123",
            first_name="Owner",
        )
        group = Group.objects.create(name="Shared Trip", created_by=owner)
        GroupMembership.objects.create(group=group, user=owner, role="owner")
        GroupMembership.objects.create(group=group, user=self.user, role="member")

        response = self.client.get("/api/v1/groups/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["groups"][0]["id"], group.id)
        self.assertEqual(response.data["groups"][0]["user_role"], "member")

    def test_group_members_hide_location_until_users_are_connected(self):
        other_user = User.objects.create_user(
            email="friend@example.com",
            password="password123",
            first_name="Friend",
        )
        group = Group.objects.create(name="Trail Team", created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user, role="owner")
        GroupMembership.objects.create(group=group, user=other_user, role="member")
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
        self.assertEqual(friend_member["role"], "member")

    def test_owner_can_remove_member(self):
        other_user = User.objects.create_user(
            email="member@example.com",
            password="password123",
            first_name="Member",
        )
        group = Group.objects.create(name="Manageable Trip", created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user, role="owner")
        GroupMembership.objects.create(group=group, user=other_user, role="member")

        response = self.client.delete(f"/api/v1/groups/{group.id}/members/{other_user.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=other_user).exists())

    def test_member_can_leave_group(self):
        owner = User.objects.create_user(
            email="tripowner@example.com",
            password="password123",
            first_name="TripOwner",
        )
        group = Group.objects.create(name="Leaveable Trip", created_by=owner)
        GroupMembership.objects.create(group=group, user=owner, role="owner")
        GroupMembership.objects.create(group=group, user=self.user, role="member")

        response = self.client.post(f"/api/v1/groups/{group.id}/leave/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.user).exists())

    def test_owner_cannot_leave_group(self):
        group = Group.objects.create(name="Owner Trip", created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user, role="owner")

        response = self.client.post(f"/api/v1/groups/{group.id}/leave/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Trip owners cannot leave. Delete the trip instead.",
        )

    def test_owner_can_delete_group(self):
        group = Group.objects.create(name="Delete Me", created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user, role="owner")

        response = self.client.delete(f"/api/v1/groups/{group.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Group.objects.filter(id=group.id).exists())


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class GroupLocationConsumerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="live@example.com",
            password="password123",
            first_name="Live",
        )
        self.group = Group.objects.create(name="RoamMap Group", created_by=self.user)
        GroupMembership.objects.create(group=self.group, user=self.user, role="owner")
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
