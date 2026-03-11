import time
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import OperationalError, transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import GroupMembership
from .models import UserLocation
from .serializers import GroupUserLocationSerializer, UserLocationSerializer

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

        locations = (
            UserLocation.objects.filter(user__group_memberships__group_id=group_id)
            .select_related('user')
            .order_by('-updated_at')
            .distinct()
        )
        serializer = GroupUserLocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
