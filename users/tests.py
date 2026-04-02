from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from groups.models import Group, GroupMembership
from users.models import User, UserConnection, UserLocation


TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class UserLocationApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="alice@example.com",
            password="password123",
            first_name="Alice",
        )
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            password="password123",
            first_name="Bob",
        )
        self.group = Group.objects.create(name="Trail Team", created_by=self.user)
        GroupMembership.objects.create(group=self.group, user=self.user)
        GroupMembership.objects.create(group=self.group, user=self.other_user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.user).access_token)}"
        )

    def test_live_location_update_marks_sharing_active(self):
        response = self.client.post(
            "/api/v1/users/location/",
            {
                "latitude": 27.6411,
                "longitude": 85.482,
                "accuracy": 5,
                "is_sharing_live": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_sharing_live"])
        self.assertIsNone(response.data["stopped_at"])

        location = UserLocation.objects.get(user=self.user)
        self.assertTrue(location.is_sharing_live)
        self.assertIsNone(location.stopped_at)

    def test_stop_sharing_preserves_last_known_coordinates(self):
        UserLocation.objects.create(
            user=self.user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.post(
            "/api/v1/users/location/",
            {
                "accuracy": 4,
                "is_sharing_live": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_sharing_live"])
        self.assertIsNotNone(response.data["stopped_at"])
        self.assertEqual(float(response.data["latitude"]), 27.643)
        self.assertEqual(float(response.data["longitude"]), 85.4731)

        location = UserLocation.objects.get(user=self.user)
        self.assertFalse(location.is_sharing_live)
        self.assertIsNotNone(location.stopped_at)

    def test_group_location_feed_returns_live_and_stopped_states(self):
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=UserConnection.Status.ACCEPTED,
        )
        UserLocation.objects.create(
            user=self.user,
            latitude=27.6411,
            longitude=85.482,
            accuracy=5,
            is_sharing_live=False,
        )
        UserLocation.objects.create(
            user=self.other_user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.get(f"/api/v1/users/location/group/{self.group.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertIn("is_sharing_live", response.data[0])
        self.assertIn("stopped_at", response.data[0])

    def test_group_location_feed_hides_non_connected_members(self):
        UserLocation.objects.create(
            user=self.other_user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.get(f"/api/v1/users/location/group/{self.group.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_group_location_lookup_returns_404_when_users_are_not_connected(self):
        UserLocation.objects.create(
            user=self.other_user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.get(
            f"/api/v1/users/location/group/{self.group.id}/",
            {"user_id": self.other_user.id},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], "Location not found.")

    def test_group_location_lookup_returns_target_location_for_connected_users(self):
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=UserConnection.Status.ACCEPTED,
        )
        UserLocation.objects.create(
            user=self.other_user,
            latitude=27.643,
            longitude=85.4731,
            accuracy=4,
            is_sharing_live=True,
        )

        response = self.client.get(
            f"/api/v1/users/location/group/{self.group.id}/",
            {"user_id": self.other_user.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], self.other_user.id)

    def test_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.post(
            "/api/v1/users/location/",
            {
                "latitude": 27.6411,
                "longitude": 85.482,
                "is_sharing_live": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserConnectionApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="alice@example.com",
            password="password123",
            first_name="Alice",
        )
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            password="password123",
            first_name="Bob",
        )
        self.third_user = User.objects.create_user(
            email="carol@example.com",
            password="password123",
            first_name="Carol",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {str(RefreshToken.for_user(self.user).access_token)}"
        )

    def test_send_connection_request_creates_pending_connection(self):
        response = self.client.post(
            "/api/v1/connections/request/",
            {"to_user_id": self.other_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        connection = UserConnection.objects.get()
        self.assertEqual(connection.from_user, self.user)
        self.assertEqual(connection.to_user, self.other_user)
        self.assertEqual(connection.status, UserConnection.Status.PENDING)

    def test_send_connection_request_rejects_reverse_duplicate(self):
        UserConnection.objects.create(
            from_user=self.other_user,
            to_user=self.user,
            status=UserConnection.Status.PENDING,
        )

        response = self.client.post(
            "/api/v1/connections/request/",
            {"to_user_id": self.other_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "This user has already sent you a connection request.",
        )

    def test_accept_connection_request_marks_connection_as_accepted(self):
        connection = UserConnection.objects.create(
            from_user=self.other_user,
            to_user=self.user,
            status=UserConnection.Status.PENDING,
        )

        response = self.client.post(f"/api/v1/connections/{connection.id}/accept/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        connection.refresh_from_db()
        self.assertEqual(connection.status, UserConnection.Status.ACCEPTED)

    def test_decline_connection_request_removes_connection(self):
        connection = UserConnection.objects.create(
            from_user=self.other_user,
            to_user=self.user,
            status=UserConnection.Status.PENDING,
        )

        response = self.client.post(f"/api/v1/connections/{connection.id}/decline/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserConnection.objects.filter(id=connection.id).exists())

    def test_list_connections_returns_accepted_connections(self):
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.other_user,
            status=UserConnection.Status.ACCEPTED,
        )
        UserConnection.objects.create(
            from_user=self.third_user,
            to_user=self.user,
            status=UserConnection.Status.PENDING,
        )

        response = self.client.get("/api/v1/connections/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["user"]["id"], self.other_user.id)

    def test_list_pending_connections_returns_incoming_requests(self):
        UserConnection.objects.create(
            from_user=self.other_user,
            to_user=self.user,
            status=UserConnection.Status.PENDING,
        )
        UserConnection.objects.create(
            from_user=self.user,
            to_user=self.third_user,
            status=UserConnection.Status.PENDING,
        )

        response = self.client.get("/api/v1/connections/pending/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["from_user"]["id"], self.other_user.id)
