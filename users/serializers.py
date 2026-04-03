from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from djoser.serializers import UserSerializer as DjoserUserSerializer
from rest_framework import serializers

from .models import User, UserConnection, UserLocation


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


class ConnectionRequestSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()


class ConnectionActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')


class UserConnectionSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = UserConnection
        fields = ('id', 'status', 'created_at', 'user')

    def get_user(self, obj):
        request = self.context['request']
        other_user = obj.to_user if obj.from_user_id == request.user.id else obj.from_user
        return ConnectionActorSerializer(other_user).data


class PendingConnectionSerializer(serializers.ModelSerializer):
    from_user = ConnectionActorSerializer(read_only=True)

    class Meta:
        model = UserConnection
        fields = ('id', 'status', 'created_at', 'from_user')
