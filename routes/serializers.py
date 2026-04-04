from rest_framework import serializers

from .models import MapRegion, RouteWaypoint, Trail, UserRoute


class MapRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapRegion
        fields = ['id', 'name', 'bounding_box', 'size_mb', 'trail_count']


class TrailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trail
        fields = ['id', 'region', 'name', 'difficulty', 'elevation_gain_m', 'geojson']


class WaypointSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteWaypoint
        fields = [
            'id',
            'route',
            'name',
            'latitude',
            'longitude',
            'elevation_m',
            'day_number',
            'arrival_time',
            'departure_time',
            'order',
            'waypoint_type',
            'is_completed',
            'is_emergency_point',
            'estimated_duration_from_prev',
            'notes',
        ]
        read_only_fields = ['id', 'route']


class RouteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRoute
        fields = [
            'id',
            'group',
            'created_by',
            'trail',
            'title',
            'direction',
            'difficulty',
            'status',
            'total_distance_km',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'group', 'created_by', 'created_at', 'updated_at']


class RouteDetailSerializer(RouteListSerializer):
    waypoints = WaypointSerializer(many=True, read_only=True)

    class Meta(RouteListSerializer.Meta):
        fields = RouteListSerializer.Meta.fields + ['waypoints']


class UserRouteWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRoute
        fields = [
            'trail',
            'title',
            'direction',
            'difficulty',
            'status',
            'total_distance_km',
            'notes',
        ]
        extra_kwargs = {
            'trail': {'required': False, 'allow_null': True},
            'status': {'required': False},
            'total_distance_km': {'required': False, 'allow_null': True},
            'notes': {'required': False, 'allow_blank': True},
        }


class WaypointReorderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order = serializers.IntegerField(min_value=1)
    day_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class WaypointReorderSerializer(serializers.Serializer):
    waypoints = WaypointReorderItemSerializer(many=True)
