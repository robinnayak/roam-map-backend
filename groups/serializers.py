from rest_framework import serializers

from .models import Group, GroupMembership, Waypoint


class GroupSerializer(serializers.ModelSerializer):
    created_by = serializers.IntegerField(source='created_by_id', read_only=True)

    class Meta:
        model = Group
        fields = (
            'id',
            'name',
            'invite_code',
            'created_by',
            'is_active',
            'expires_at',
            'created_at',
        )
        read_only_fields = (
            'id',
            'invite_code',
            'created_by',
            'is_active',
            'expires_at',
            'created_at',
        )


class CreateGroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class JoinGroupSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=32)


class GroupMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    location = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = (
            'user_id',
            'email',
            'first_name',
            'last_name',
            'joined_at',
            'location',
        )

    def get_location(self, obj):
        connected_user_ids = self.context.get('connected_user_ids', set())
        if obj.user_id not in connected_user_ids:
            return None

        location = getattr(obj.user, 'location', None)
        if location is None:
            return None
        return {
            'latitude': location.latitude,
            'longitude': location.longitude,
            'accuracy': location.accuracy,
            'is_sharing_live': location.is_sharing_live,
            'stopped_at': location.stopped_at,
            'updated_at': location.updated_at,
        }


class CreateWaypointSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class WaypointSerializer(serializers.ModelSerializer):
    created_by = serializers.IntegerField(source='created_by_id', read_only=True)
    group = serializers.IntegerField(source='group_id', read_only=True)

    class Meta:
        model = Waypoint
        fields = (
            'id',
            'group',
            'created_by',
            'label',
            'latitude',
            'longitude',
            'created_at',
        )
