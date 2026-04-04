import logging

from django.utils import timezone
from groups.models import GroupMembership
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
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

    def get(self, request):
        group_id = request.query_params.get('group')
        if not group_id:
            raise ValidationError({'group': ['This query parameter is required.']})

        try:
            group_id_int = int(group_id)
        except (TypeError, ValueError):
            raise ValidationError({'group': ['A valid group id is required.']})

        is_member = GroupMembership.objects.filter(
            group_id=group_id_int,
            user=request.user,
        ).exists()
        if not is_member:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        active_only = request.query_params.get('active', 'true').lower() != 'false'
        queryset = SOSAlert.objects.filter(group_id=group_id_int)
        if active_only:
            queryset = queryset.filter(is_active=True)

        alerts = queryset.order_by('-triggered_at', '-id')
        return Response(SOSAlertSerializer(alerts, many=True).data, status=status.HTTP_200_OK)

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

        if alert.user_id != request.user.id:
            return Response(
                {'detail': 'Only the user who triggered this SOS can resolve it.'},
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
