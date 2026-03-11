from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from djoser.serializers import UserSerializer as DjoserUserSerializer
from rest_framework import serializers

from .models import User, UserLocation


class UserCreateSerializer(DjoserUserCreateSerializer):
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'password')


class UserSerializer(DjoserUserSerializer):
    class Meta(DjoserUserSerializer.Meta):
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone')


class UserLocationSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    is_sharing_live = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = UserLocation
        fields = (
            'latitude',
            'longitude',
            'accuracy',
            'is_sharing_live',
            'stopped_at',
            'updated_at',
        )
        read_only_fields = ('stopped_at', 'updated_at')

    def validate(self, attrs):
        is_sharing_live = attrs.get('is_sharing_live', True)
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')

        if is_sharing_live and (latitude is None or longitude is None):
            raise serializers.ValidationError(
                'Latitude and longitude are required while live sharing is active.'
            )

        return attrs


class GroupUserLocationSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserLocation
        fields = (
            'user_id',
            'email',
            'first_name',
            'last_name',
            'latitude',
            'longitude',
            'accuracy',
            'is_sharing_live',
            'stopped_at',
            'updated_at',
        )
