from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from emergency.models import SOSAlert
from groups.models import Group, GroupMembership
from routes.models import MapRegion, Trail
from users.models import User, UserLocation


class BackendRegressionSmokeTests(APITestCase):
    def _create_user(self, email: str, password: str = "Pass1234!"):
        return User.objects.create_user(email=email, password=password)

    def _jwt_login(self, email: str, password: str = "Pass1234!"):
        response = self.client.post(
            "/api/v1/auth/jwt/create/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data.get("access")
        self.assertTrue(token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_health_check_is_public(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "ok")

    def test_auth_register_login_and_invalid_login(self):
        register = self.client.post(
            "/api/v1/auth/users/",
            {"email": "reg@example.com", "password": "Pass1234!"},
            format="json",
        )
        self.assertEqual(register.status_code, status.HTTP_201_CREATED)

        login_ok = self.client.post(
            "/api/v1/auth/jwt/create/",
            {"email": "reg@example.com", "password": "Pass1234!"},
            format="json",
        )
        self.assertEqual(login_ok.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_ok.data)
        self.assertIn("refresh", login_ok.data)

        login_bad = self.client.post(
            "/api/v1/auth/jwt/create/",
            {"email": "reg@example.com", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(login_bad.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoints_require_authentication(self):
        user = self._create_user("owner@example.com")
        group = Group.objects.create(name="Alpha", created_by=user)
        GroupMembership.objects.create(group=group, user=user)
        alert = SOSAlert.objects.create(
            user=user,
            group=group,
            latitude=Decimal("27.700000"),
            longitude=Decimal("85.300000"),
        )

        region = MapRegion.objects.create(
            name="Kathmandu Valley",
            bounding_box={"type": "bbox", "value": [85.2, 27.6, 85.5, 27.9]},
            size_mb=Decimal("42.50"),
            trail_count=1,
        )
        trail = Trail.objects.create(
            region=region,
            name="Shivapuri Ridge",
            difficulty="medium",
            elevation_gain_m=800,
            geojson={"type": "LineString", "coordinates": [[85.3, 27.8], [85.4, 27.85]]},
        )

        checks = [
            ("post", "/api/v1/users/location/", {"latitude": "27.700001", "longitude": "85.300001"}),
            ("post", "/api/v1/groups/", {"name": "Unauth Group"}),
            ("get", "/api/v1/groups/join/", None),
            ("get", f"/api/v1/groups/{group.id}/members/", None),
            ("get", "/api/v1/routes/regions/", None),
            ("get", f"/api/v1/routes/trails/{region.id}/", None),
            ("get", f"/api/v1/routes/trails/detail/{trail.id}/", None),
            ("get", f"/api/v1/routes/weather/{region.id}/", None),
            (
                "post",
                "/api/v1/emergency/sos/",
                {"group": group.id, "latitude": "27.700000", "longitude": "85.300000"},
            ),
            ("patch", f"/api/v1/emergency/sos/{alert.id}/resolve/", None),
        ]

        for method, path, payload in checks:
            response = getattr(self.client, method)(path, payload, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                msg=f"{method.upper()} {path} expected 401, got {response.status_code}",
            )

    def test_authenticated_regression_smoke_flow(self):
        user = self._create_user("owner2@example.com")
        self._jwt_login(user.email)

        create_group = self.client.post("/api/v1/groups/", {"name": "Rescue Team"}, format="json")
        self.assertEqual(create_group.status_code, status.HTTP_201_CREATED)
        group_id = create_group.data["id"]

        update_location = self.client.post(
            "/api/v1/users/location/",
            {"latitude": "27.717200", "longitude": "85.324000", "accuracy": 5.5},
            format="json",
        )
        self.assertEqual(update_location.status_code, status.HTTP_200_OK)

        group_locations = self.client.get(f"/api/v1/users/location/group/{group_id}/")
        self.assertEqual(group_locations.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(group_locations.data), 1)

        members = self.client.get(f"/api/v1/groups/{group_id}/members/")
        self.assertEqual(members.status_code, status.HTTP_200_OK)
        self.assertIn("members", members.data)

        waypoint = self.client.post(
            f"/api/v1/groups/{group_id}/waypoints/",
            {"label": "Camp", "latitude": "27.721000", "longitude": "85.330000"},
            format="json",
        )
        self.assertEqual(waypoint.status_code, status.HTTP_201_CREATED)

        region = MapRegion.objects.create(
            name="Langtang",
            bounding_box={"type": "bbox", "value": [85.4, 28.0, 85.8, 28.4]},
            size_mb=Decimal("71.20"),
            trail_count=1,
        )
        trail = Trail.objects.create(
            region=region,
            name="Kyanjin Loop",
            difficulty="hard",
            elevation_gain_m=1200,
            geojson={"type": "LineString", "coordinates": [[85.55, 28.2], [85.62, 28.27]]},
        )

        regions = self.client.get("/api/v1/routes/regions/")
        self.assertEqual(regions.status_code, status.HTTP_200_OK)

        trails = self.client.get(f"/api/v1/routes/trails/{region.id}/")
        self.assertEqual(trails.status_code, status.HTTP_200_OK)
        self.assertEqual(trails.data["type"], "FeatureCollection")

        trail_detail = self.client.get(f"/api/v1/routes/trails/detail/{trail.id}/")
        self.assertEqual(trail_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(trail_detail.data["id"], trail.id)

        weather = self.client.get(f"/api/v1/routes/weather/{region.id}/")
        self.assertEqual(weather.status_code, status.HTTP_200_OK)
        self.assertEqual(weather.data["region_id"], region.id)

        trigger_sos = self.client.post(
            "/api/v1/emergency/sos/",
            {"group": group_id, "latitude": "27.717200", "longitude": "85.324000"},
            format="json",
        )
        self.assertEqual(trigger_sos.status_code, status.HTTP_201_CREATED)
        alert_id = trigger_sos.data["id"]

        resolve_sos = self.client.patch(f"/api/v1/emergency/sos/{alert_id}/resolve/", format="json")
        self.assertEqual(resolve_sos.status_code, status.HTTP_200_OK)
        self.assertFalse(resolve_sos.data["is_active"])

        self.assertTrue(UserLocation.objects.filter(user=user).exists())

    def test_group_authorization_failures_return_403(self):
        owner = self._create_user("owner3@example.com")
        outsider = self._create_user("outsider3@example.com")
        group = Group.objects.create(name="Members Only", created_by=owner)
        GroupMembership.objects.create(group=group, user=owner)

        self._jwt_login(outsider.email)

        locations = self.client.get(f"/api/v1/users/location/group/{group.id}/")
        self.assertEqual(locations.status_code, status.HTTP_403_FORBIDDEN)

        members = self.client.get(f"/api/v1/groups/{group.id}/members/")
        self.assertEqual(members.status_code, status.HTTP_403_FORBIDDEN)
