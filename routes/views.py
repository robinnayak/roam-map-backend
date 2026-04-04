from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import Group
from groups.permissions import IsGroupOwner, is_group_member

from .models import MapRegion, RouteWaypoint, Trail, UserRoute
from .serializers import (
    MapRegionSerializer,
    RouteDetailSerializer,
    RouteListSerializer,
    TrailSerializer,
    UserRouteWriteSerializer,
    WaypointReorderSerializer,
    WaypointSerializer,
)


def get_group_for_user(group_id, user):
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return None, Response({'detail': 'Group not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not is_group_member(user, group.id):
        return None, Response(
            {'detail': 'You are not a member of this group.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    return group, None


def get_route_for_group(group_id, route_id):
    try:
        route = UserRoute.objects.select_related('group', 'created_by', 'trail').prefetch_related(
            'waypoints'
        ).get(id=route_id, group_id=group_id)
    except UserRoute.DoesNotExist:
        return None
    return route


class MapRegionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        regions = MapRegion.objects.all().order_by('name')
        serializer = MapRegionSerializer(regions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TrailGeoJSONView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, region_id):
        if not MapRegion.objects.filter(id=region_id).exists():
            return Response({'detail': 'Region not found.'}, status=status.HTTP_404_NOT_FOUND)

        trails = Trail.objects.filter(region_id=region_id).order_by('name')
        features = [
            {
                'type': 'Feature',
                'id': trail.id,
                'geometry': trail.geojson,
                'properties': {
                    'trail_id': trail.id,
                    'name': trail.name,
                    'difficulty': trail.difficulty,
                    'elevation_gain_m': trail.elevation_gain_m,
                    'region_id': trail.region_id,
                },
            }
            for trail in trails
        ]
        payload = {
            'type': 'FeatureCollection',
            'features': features,
        }
        return Response(payload, status=status.HTTP_200_OK)


class TrailDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, trail_id):
        try:
            trail = Trail.objects.select_related('region').get(id=trail_id)
        except Trail.DoesNotExist:
            return Response({'detail': 'Trail not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TrailSerializer(trail)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RegionWeatherView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    CACHE_TTL_SECONDS = 3600

    def get(self, request, region_id):
        try:
            region = MapRegion.objects.get(id=region_id)
        except MapRegion.DoesNotExist:
            return Response({'detail': 'Region not found.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f'region_weather:{region_id}'
        cached_payload = cache.get(cache_key)
        if cached_payload:
            return Response(cached_payload, status=status.HTTP_200_OK)

        payload = {
            'region_id': region.id,
            'region_name': region.name,
            'forecast': [],
            'source': 'placeholder',
            'note': 'Weather provider integration pending. Response is cached for 1 hour.',
        }
        cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        return Response(payload, status=status.HTTP_200_OK)


class GroupRouteListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group, error_response = get_group_for_user(group_id, request.user)
        if error_response is not None:
            return error_response

        routes = UserRoute.objects.filter(group=group).select_related('created_by', 'trail')
        serializer = RouteListSerializer(routes, many=True)
        return Response({'routes': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, group_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Group not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserRouteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = serializer.save(group=group, created_by=request.user)
        return Response(RouteDetailSerializer(route).data, status=status.HTTP_201_CREATED)


class GroupRouteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id, route_id):
        group, error_response = get_group_for_user(group_id, request.user)
        if error_response is not None:
            return error_response

        route = get_route_for_group(group.id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(RouteDetailSerializer(route).data, status=status.HTTP_200_OK)

    def patch(self, request, group_id, route_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        try:
            Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Group not found.'}, status=status.HTTP_404_NOT_FOUND)

        route = get_route_for_group(group_id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserRouteWriteSerializer(route, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        route.refresh_from_db()
        return Response(RouteDetailSerializer(route).data, status=status.HTTP_200_OK)

    def delete(self, request, group_id, route_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        try:
            Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Group not found.'}, status=status.HTTP_404_NOT_FOUND)

        route = get_route_for_group(group_id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        route.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteWaypointListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, route_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        try:
            Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response({'detail': 'Group not found.'}, status=status.HTTP_404_NOT_FOUND)

        route = get_route_for_group(group_id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WaypointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        waypoint = serializer.save(route=route)
        return Response(WaypointSerializer(waypoint).data, status=status.HTTP_201_CREATED)


class RouteWaypointDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, group_id, route_id, wp_id):
        route = get_route_for_group(group_id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_owner = IsGroupOwner().has_permission(request, self)
        if not is_owner:
            group, error_response = get_group_for_user(group_id, request.user)
            if error_response is not None:
                return error_response
            if group.id != route.group_id:
                return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

            allowed_member_fields = {'is_completed'}
            payload_keys = set(request.data.keys())
            if not payload_keys or not payload_keys.issubset(allowed_member_fields):
                return Response(
                    {'detail': IsGroupOwner.message},
                    status=status.HTTP_403_FORBIDDEN,
                )

        waypoint = RouteWaypoint.objects.filter(
            id=wp_id,
            route_id=route_id,
            route__group_id=group_id,
        ).first()
        if waypoint is None:
            return Response({'detail': 'Waypoint not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WaypointSerializer(waypoint, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WaypointSerializer(waypoint).data, status=status.HTTP_200_OK)

    def delete(self, request, group_id, route_id, wp_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        waypoint = RouteWaypoint.objects.filter(
            id=wp_id,
            route_id=route_id,
            route__group_id=group_id,
        ).first()
        if waypoint is None:
            return Response({'detail': 'Waypoint not found.'}, status=status.HTTP_404_NOT_FOUND)

        waypoint.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RouteWaypointReorderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, route_id):
        owner_permission = IsGroupOwner()
        if not owner_permission.has_permission(request, self):
            return Response({'detail': owner_permission.message}, status=status.HTTP_403_FORBIDDEN)

        route = get_route_for_group(group_id, route_id)
        if route is None:
            return Response({'detail': 'Route not found.'}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data
        if isinstance(payload, list):
            payload = {'waypoints': payload}

        serializer = WaypointReorderSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        reorder_items = serializer.validated_data['waypoints']
        waypoint_map = {
            waypoint.id: waypoint
            for waypoint in RouteWaypoint.objects.filter(route=route, id__in=[item['id'] for item in reorder_items])
        }
        if len(waypoint_map) != len(reorder_items):
            return Response(
                {'detail': 'One or more waypoints were not found for this route.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in reorder_items:
            waypoint = waypoint_map[item['id']]
            waypoint.order = item['order']
            waypoint.day_number = item.get('day_number')
            waypoint.save(update_fields=['order', 'day_number'])

        route.refresh_from_db()
        return Response(RouteDetailSerializer(route).data, status=status.HTTP_200_OK)
