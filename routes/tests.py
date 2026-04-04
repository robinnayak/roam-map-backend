from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from groups.models import Group, GroupMembership
from users.models import User

from .models import RouteWaypoint, UserRoute


class RoutePlanningApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email='owner-route@example.com',
            password='password123',
            first_name='Owner',
        )
        self.member = User.objects.create_user(
            email='member-route@example.com',
            password='password123',
            first_name='Member',
        )
        self.non_member = User.objects.create_user(
            email='outsider-route@example.com',
            password='password123',
            first_name='Outsider',
        )
        self.group = Group.objects.create(name='Route Team', created_by=self.owner)
        GroupMembership.objects.create(group=self.group, user=self.owner, role='owner')
        GroupMembership.objects.create(group=self.group, user=self.member, role='member')

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(user).access_token)}'
        )

    def create_route(self, created_by=None, **overrides):
        return UserRoute.objects.create(
            group=self.group,
            created_by=created_by or self.owner,
            title=overrides.get('title', 'Annapurna Segment'),
            direction=overrides.get('direction', UserRoute.Direction.OUTBOUND),
            difficulty=overrides.get('difficulty', UserRoute.Difficulty.MODERATE),
            status=overrides.get('status', UserRoute.Status.DRAFT),
            total_distance_km=overrides.get('total_distance_km', 18.2),
            notes=overrides.get('notes', 'Carry extra water'),
        )

    def create_waypoint(self, route, **overrides):
        return RouteWaypoint.objects.create(
            route=route,
            name=overrides.get('name', 'Camp'),
            latitude=overrides.get('latitude', 28.209),
            longitude=overrides.get('longitude', 83.985),
            elevation_m=overrides.get('elevation_m'),
            day_number=overrides.get('day_number'),
            arrival_time=overrides.get('arrival_time'),
            departure_time=overrides.get('departure_time'),
            order=overrides.get('order', 1),
            waypoint_type=overrides.get(
                'waypoint_type',
                RouteWaypoint.WaypointType.CAMPSITE,
            ),
            is_completed=overrides.get('is_completed', False),
            is_emergency_point=overrides.get('is_emergency_point', False),
            estimated_duration_from_prev=overrides.get('estimated_duration_from_prev'),
            notes=overrides.get('notes', ''),
        )

    def test_member_can_list_and_retrieve_routes(self):
        route = self.create_route()
        self.create_waypoint(route, name='Checkpoint 1', day_number=1, order=1)

        self.authenticate(self.member)
        list_response = self.client.get(f'/api/v1/groups/{self.group.id}/routes/')
        detail_response = self.client.get(f'/api/v1/groups/{self.group.id}/routes/{route.id}/')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['routes']), 1)
        self.assertEqual(detail_response.data['id'], route.id)
        self.assertEqual(len(detail_response.data['waypoints']), 1)

    def test_non_member_cannot_access_routes(self):
        route = self.create_route()

        self.authenticate(self.non_member)
        list_response = self.client.get(f'/api/v1/groups/{self.group.id}/routes/')
        detail_response = self.client.get(f'/api/v1/groups/{self.group.id}/routes/{route.id}/')

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(detail_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_create_edit_and_delete_route(self):
        self.authenticate(self.owner)

        create_response = self.client.post(
            f'/api/v1/groups/{self.group.id}/routes/',
            {
                'title': 'Mardi Himal Plan',
                'direction': UserRoute.Direction.OUTBOUND,
                'difficulty': UserRoute.Difficulty.HARD,
                'status': UserRoute.Status.ACTIVE,
                'total_distance_km': 24.5,
                'notes': 'Early alpine start',
            },
            format='json',
        )
        route_id = create_response.data['id']
        patch_response = self.client.patch(
            f'/api/v1/groups/{self.group.id}/routes/{route_id}/',
            {'status': UserRoute.Status.COMPLETED, 'title': 'Mardi Himal Complete'},
            format='json',
        )
        delete_response = self.client.delete(f'/api/v1/groups/{self.group.id}/routes/{route_id}/')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(UserRoute.objects.filter(id=route_id).exists())

    def test_member_cannot_create_edit_or_delete_route(self):
        route = self.create_route()
        self.authenticate(self.member)

        create_response = self.client.post(
            f'/api/v1/groups/{self.group.id}/routes/',
            {
                'title': 'Blocked Route',
                'direction': UserRoute.Direction.OUTBOUND,
                'difficulty': UserRoute.Difficulty.EASY,
            },
            format='json',
        )
        patch_response = self.client.patch(
            f'/api/v1/groups/{self.group.id}/routes/{route.id}/',
            {'status': UserRoute.Status.ARCHIVED},
            format='json',
        )
        delete_response = self.client.delete(f'/api/v1/groups/{self.group.id}/routes/{route.id}/')

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_waypoints_are_sorted_by_day_number_and_order(self):
        route = self.create_route()
        self.create_waypoint(route, name='Day 2 Stop B', day_number=2, order=2)
        self.create_waypoint(route, name='Day 1 Start', day_number=1, order=1)
        self.create_waypoint(route, name='Day 2 Stop A', day_number=2, order=1)

        self.authenticate(self.member)
        response = self.client.get(f'/api/v1/groups/{self.group.id}/routes/{route.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [waypoint['name'] for waypoint in response.data['waypoints']],
            ['Day 1 Start', 'Day 2 Stop A', 'Day 2 Stop B'],
        )

    def test_member_can_mark_waypoint_completed(self):
        route = self.create_route()
        waypoint = self.create_waypoint(route, name='Dhampus', day_number=1, order=1)

        self.authenticate(self.member)
        response = self.client.patch(
            f'/api/v1/groups/{self.group.id}/routes/{route.id}/waypoints/{waypoint.id}/',
            {'is_completed': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        waypoint.refresh_from_db()
        self.assertTrue(waypoint.is_completed)
        self.assertTrue(response.data['is_completed'])

    def test_member_cannot_edit_other_waypoint_fields(self):
        route = self.create_route()
        waypoint = self.create_waypoint(route, name='Dhampus', day_number=1, order=1)

        self.authenticate(self.member)
        response = self.client.patch(
            f'/api/v1/groups/{self.group.id}/routes/{route.id}/waypoints/{waypoint.id}/',
            {'name': 'New Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        waypoint.refresh_from_db()
        self.assertEqual(waypoint.name, 'Dhampus')

    def test_reorder_endpoint_updates_order_values(self):
        route = self.create_route()
        wp1 = self.create_waypoint(route, name='First', day_number=1, order=1)
        wp2 = self.create_waypoint(route, name='Second', day_number=1, order=2)

        self.authenticate(self.owner)
        response = self.client.post(
            f'/api/v1/groups/{self.group.id}/routes/{route.id}/waypoints/reorder/',
            [
                {'id': wp1.id, 'order': 2, 'day_number': 2},
                {'id': wp2.id, 'order': 1, 'day_number': 1},
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wp1.refresh_from_db()
        wp2.refresh_from_db()
        self.assertEqual((wp1.order, wp1.day_number), (2, 2))
        self.assertEqual((wp2.order, wp2.day_number), (1, 1))

    def test_delete_route_cascades_to_waypoints(self):
        route = self.create_route()
        waypoint = self.create_waypoint(route, name='Cascade Check', day_number=1, order=1)

        self.authenticate(self.owner)
        response = self.client.delete(f'/api/v1/groups/{self.group.id}/routes/{route.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RouteWaypoint.objects.filter(id=waypoint.id).exists())
