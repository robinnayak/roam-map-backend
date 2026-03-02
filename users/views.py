import time

from django.db import OperationalError, transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import GroupMembership
from .models import UserLocation
from .serializers import GroupUserLocationSerializer, UserLocationSerializer


class UpdateLocationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # SQLite can briefly lock under concurrent writes. Retry a few times
        # before failing to avoid noisy transient 500s in local/dev usage.
        retries = 4
        retry_delay_seconds = 0.1
        for attempt in range(retries):
            try:
                with transaction.atomic():
                    location, _ = UserLocation.objects.update_or_create(
                        user=request.user,
                        defaults=serializer.validated_data,
                    )
                break
            except OperationalError as exc:
                is_locked = 'database is locked' in str(exc).lower()
                is_last_attempt = attempt == retries - 1
                if not is_locked or is_last_attempt:
                    raise
                time.sleep(retry_delay_seconds)

        response_serializer = UserLocationSerializer(location)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


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
