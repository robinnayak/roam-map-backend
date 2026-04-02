import time
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import GroupMembership
from .models import (
    User,
    UserConnection,
    UserLocation,
    get_connected_user_ids,
    get_connection_lookup,
)
from .serializers import (
    ConnectionRequestSerializer,
    GroupUserLocationSerializer,
    PendingConnectionSerializer,
    UserConnectionSerializer,
    UserLocationSerializer,
)

logger = logging.getLogger(__name__)


class UpdateLocationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        is_sharing_live = validated.get('is_sharing_live', True)

        # SQLite can briefly lock under concurrent writes. Retry a few times
        # before failing to avoid noisy transient 500s in local/dev usage.
        retries = 4
        retry_delay_seconds = 0.1
        for attempt in range(retries):
            try:
                with transaction.atomic():
                    defaults = {
                        'accuracy': validated.get('accuracy'),
                        'is_sharing_live': is_sharing_live,
                        'stopped_at': None if is_sharing_live else timezone.now(),
                    }
                    if validated.get('latitude') is not None:
                        defaults['latitude'] = validated['latitude']
                    if validated.get('longitude') is not None:
                        defaults['longitude'] = validated['longitude']

                    if is_sharing_live:
                        location, _ = UserLocation.objects.update_or_create(
                            user=request.user,
                            defaults=defaults,
                        )
                    else:
                        try:
                            location = UserLocation.objects.select_for_update().get(
                                user=request.user
                            )
                        except UserLocation.DoesNotExist:
                            return Response(
                                {
                                    'detail': (
                                        'Cannot stop live sharing before a first '
                                        'location has been recorded.'
                                    )
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        for field, value in defaults.items():
                            setattr(location, field, value)
                        location.save(
                            update_fields=[
                                'accuracy',
                                'is_sharing_live',
                                'stopped_at',
                                'updated_at',
                            ]
                        )
                break
            except OperationalError as exc:
                is_locked = 'database is locked' in str(exc).lower()
                is_last_attempt = attempt == retries - 1
                if not is_locked or is_last_attempt:
                    raise
                time.sleep(retry_delay_seconds)

        self._broadcast_location_update(location)
        response_serializer = GroupUserLocationSerializer(location)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def _broadcast_location_update(self, location: UserLocation) -> None:
        group_ids = list(
            GroupMembership.objects.filter(user=location.user).values_list(
                'group_id',
                flat=True,
            )
        )
        if not group_ids:
            return

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        payload = GroupUserLocationSerializer(location).data
        for group_id in group_ids:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"group_{group_id}",
                    {
                        "type": "group_location",
                        "payload": {
                            "group_id": group_id,
                            **payload,
                        },
                    },
                )
            except Exception:
                # Realtime transport must not break core location writes.
                logger.warning(
                    "Failed to broadcast group location update",
                    extra={
                        "group_id": group_id,
                        "user_id": location.user_id,
                    },
                    exc_info=True,
                )


class GroupLocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        is_member = GroupMembership.objects.filter(
            group_id=group_id,
            user=request.user,
        ).exists()
        if not is_member:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        target_user_id = request.query_params.get('user_id')
        connected_user_ids = get_connected_user_ids(request.user.id)
        locations = (
            UserLocation.objects.filter(user__group_memberships__group_id=group_id)
            .filter(user_id__in=connected_user_ids)
            .select_related('user')
            .order_by('-updated_at')
            .distinct()
        )
        if target_user_id is not None:
            try:
                target_user_id = int(target_user_id)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'user_id must be an integer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_target_member = GroupMembership.objects.filter(
                group_id=group_id,
                user_id=target_user_id,
            ).exists()
            if not is_target_member or target_user_id not in connected_user_ids:
                return Response(
                    {'detail': 'Location not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            location = get_object_or_404(locations, user_id=target_user_id)
            serializer = GroupUserLocationSerializer(location)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = GroupUserLocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConnectionRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ConnectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user = get_object_or_404(User, id=serializer.validated_data['to_user_id'])
        if to_user.id == request.user.id:
            return Response(
                {'detail': 'You cannot send a connection request to yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_connection = UserConnection.objects.filter(
            get_connection_lookup(request.user.id, to_user.id)
        ).first()
        if existing_connection is not None:
            if existing_connection.status == UserConnection.Status.ACCEPTED:
                detail = 'You are already connected to this user.'
            elif existing_connection.status == UserConnection.Status.PENDING:
                if existing_connection.from_user_id == request.user.id:
                    detail = 'A connection request is already pending.'
                else:
                    detail = 'This user has already sent you a connection request.'
            else:
                detail = 'This connection is blocked.'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        connection = UserConnection.objects.create(
            from_user=request.user,
            to_user=to_user,
            status=UserConnection.Status.PENDING,
        )
        response_serializer = PendingConnectionSerializer(connection)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ConnectionAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, connection_id):
        connection = get_object_or_404(
            UserConnection,
            id=connection_id,
            to_user=request.user,
            status=UserConnection.Status.PENDING,
        )
        connection.status = UserConnection.Status.ACCEPTED
        connection.save(update_fields=['status'])
        serializer = UserConnectionSerializer(connection, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConnectionDeclineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, connection_id):
        connection = get_object_or_404(
            UserConnection.objects.filter(
                id=connection_id,
            ).filter(
                Q(from_user=request.user) | Q(to_user=request.user)
            ),
        )
        connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConnectionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        connections = (
            UserConnection.objects.filter(
                status=UserConnection.Status.ACCEPTED,
            )
            .filter(Q(from_user=request.user) | Q(to_user=request.user))
            .select_related('from_user', 'to_user')
            .order_by('-created_at')
        )
        serializer = UserConnectionSerializer(
            connections,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class PendingConnectionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        connections = (
            UserConnection.objects.filter(
                to_user=request.user,
                status=UserConnection.Status.PENDING,
            )
            .select_related('from_user')
            .order_by('-created_at')
        )
        serializer = PendingConnectionSerializer(connections, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
