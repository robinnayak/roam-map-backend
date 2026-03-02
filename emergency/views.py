import logging

from django.utils import timezone
from groups.models import GroupMembership
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SOSAlert
from .serializers import SOSAlertSerializer

logger = logging.getLogger(__name__)


def fanout_sos_notification(alert) -> None:
    # Hook for future push integration; currently logs alert fan-out intent.
    logger.info(
        'SOS fanout queued for group=%s alert_id=%s user_id=%s',
        alert.group_id,
        alert.id,
        alert.user_id,
    )


class TriggerSOSView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SOSAlertSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        alert = serializer.save()

        fanout_sos_notification(alert)

        return Response(
            SOSAlertSerializer(alert).data,
            status=status.HTTP_201_CREATED,
        )


class ResolveSOSView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, alert_id):
        try:
            alert = SOSAlert.objects.select_related('group').get(id=alert_id)
        except SOSAlert.DoesNotExist:
            return Response(
                {'detail': 'SOS alert not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_member = GroupMembership.objects.filter(
            group=alert.group,
            user=request.user,
        ).exists()
        if not is_member:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not alert.is_active:
            return Response(
                {'detail': 'SOS alert is already resolved.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        alert.is_active = False
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['is_active', 'resolved_at'])

        return Response(SOSAlertSerializer(alert).data, status=status.HTTP_200_OK)
