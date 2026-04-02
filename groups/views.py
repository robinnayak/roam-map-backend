from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Group, GroupMembership
from .serializers import (
    CreateGroupSerializer,
    CreateWaypointSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    JoinGroupSerializer,
    WaypointSerializer,
)
from users.models import get_connected_user_ids


class CreateGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_group_count = Group.objects.filter(
            created_by=request.user,
            is_active=True,
        ).count()
        if active_group_count >= 3:
            return Response(
                {'detail': 'You can only create up to 3 active groups at a time.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            group = Group.objects.create(
                name=serializer.validated_data['name'],
                created_by=request.user,
            )
            GroupMembership.objects.get_or_create(group=group, user=request.user)

        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)


class JoinGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = JoinGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite_code = serializer.validated_data['invite_code']
        try:
            group = Group.objects.get(invite_code=invite_code)
        except Group.DoesNotExist:
            return Response(
                {'detail': 'Invalid invite code.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        _, created = GroupMembership.objects.get_or_create(group=group, user=request.user)
        response = {
            'group': GroupSerializer(group).data,
            'joined': created,
        }
        return Response(
            response,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GroupMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
        if not is_member:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        memberships = (
            GroupMembership.objects.filter(group=group)
            .select_related('user', 'user__location')
            .order_by('joined_at')
        )
        members_data = GroupMemberSerializer(
            memberships,
            many=True,
            context={'connected_user_ids': get_connected_user_ids(request.user.id)},
        ).data
        return Response(
            {
                'group': GroupSerializer(group).data,
                'members': members_data,
            },
            status=status.HTTP_200_OK,
        )


class WaypointView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
        if not is_member:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateWaypointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        waypoint = group.waypoints.create(
            created_by=request.user,
            **serializer.validated_data,
        )
        return Response(WaypointSerializer(waypoint).data, status=status.HTTP_201_CREATED)
