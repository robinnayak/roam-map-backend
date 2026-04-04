from django.db import transaction
from django.db.models import Count, Prefetch, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Group, GroupMembership, GroupPlannerTask
from .permissions import is_group_member
from .serializers import (
    CreateGroupSerializer,
    CreateWaypointSerializer,
    GroupPlannerTaskSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    JoinGroupSerializer,
    PlannerTaskAssignSerializer,
    PlannerTaskCreateSerializer,
    PlannerTaskStatusSerializer,
    PlannerTaskUpdateSerializer,
    WaypointSerializer,
)
from users.models import get_connected_user_ids


def ensure_owner_membership(group: Group) -> GroupMembership:
    membership, created = GroupMembership.objects.get_or_create(
        group=group,
        user=group.created_by,
        defaults={'role': GroupMembership.Role.OWNER},
    )
    if not created and membership.role != GroupMembership.Role.OWNER:
        membership.role = GroupMembership.Role.OWNER
        membership.save(update_fields=['role'])
    return membership


def get_group_queryset_for_user(user):
    return (
        Group.objects.filter(Q(created_by=user) | Q(memberships__user=user))
        .distinct()
        .annotate(member_count=Count('memberships', distinct=True))
        .prefetch_related(
            Prefetch(
                'memberships',
                queryset=GroupMembership.objects.filter(user=user).only(
                    'group_id',
                    'user_id',
                    'role',
                ),
                to_attr='prefetched_memberships',
            )
        )
        .order_by('-created_at')
    )


def get_accessible_group_for_user(group_id: int, user):
    group = (
        Group.objects.filter(id=group_id)
        .annotate(member_count=Count('memberships', distinct=True))
        .prefetch_related(
            Prefetch(
                'memberships',
                queryset=GroupMembership.objects.filter(user=user).only(
                    'group_id',
                    'user_id',
                    'role',
                ),
                to_attr='prefetched_memberships',
            )
        )
        .first()
    )
    if group is None:
        return None

    memberships = getattr(group, 'prefetched_memberships', [])
    if group.created_by_id == user.id:
        ensure_owner_membership(group)
        if getattr(group, 'member_count', 0) == 0:
            group.member_count = 1
        group.prefetched_memberships = [
            membership
            for membership in memberships
            if membership.user_id == user.id
        ] or [GroupMembership(group=group, user=user, role=GroupMembership.Role.OWNER)]
        return group

    if memberships:
        return group

    return None


def user_is_group_owner(group: Group, user) -> bool:
    if group.created_by_id == user.id:
        return True
    memberships = getattr(group, 'prefetched_memberships', None)
    if memberships is not None:
        return any(
            membership.user_id == user.id and membership.role == GroupMembership.Role.OWNER
            for membership in memberships
        )
    return GroupMembership.objects.filter(
        group=group,
        user=user,
        role=GroupMembership.Role.OWNER,
    ).exists()


def get_planner_group_for_user(group_id: int, user):
    group = (
        Group.objects.filter(id=group_id)
        .annotate(member_count=Count('memberships', distinct=True))
        .prefetch_related(
            Prefetch(
                'memberships',
                queryset=GroupMembership.objects.filter(user=user).only(
                    'group_id',
                    'user_id',
                    'role',
                ),
                to_attr='prefetched_memberships',
            )
        )
        .first()
    )
    if group is None:
        return None

    if not is_group_member(user, group_id):
        return None

    ensure_owner_membership(group)
    return group


def get_planner_task_for_group(group: Group, task_id: int):
    return (
        GroupPlannerTask.objects.filter(group=group, id=task_id)
        .select_related('created_by', 'assigned_to')
        .first()
    )


def serialize_planner_tasks(group: Group):
    tasks = list(
        group.planner_tasks.select_related('created_by', 'assigned_to').order_by(
            'category',
            'sort_order',
            'created_at',
            'id',
        )
    )
    grouped = []
    seen_categories = []
    for task in tasks:
        if task.category not in seen_categories:
            seen_categories.append(task.category)

    for category in seen_categories:
        category_tasks = [task for task in tasks if task.category == category]
        grouped.append(
            {
                'category': category,
                'tasks': GroupPlannerTaskSerializer(category_tasks, many=True).data,
            }
        )

    return grouped


class GroupListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        created_groups = Group.objects.filter(created_by=request.user).only('id', 'created_by_id')
        for group in created_groups:
            ensure_owner_membership(group)

        groups = get_group_queryset_for_user(request.user)
        serializer = GroupSerializer(groups, many=True, context={'user': request.user})
        return Response({'groups': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_group_count = Group.objects.filter(
            created_by=request.user,
            is_active=True,
        ).count()
        if active_group_count >= 3:
            return Response(
                {'detail': 'You already created 3 active trips. Delete one to create a new trip.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            group = Group.objects.create(
                name=serializer.validated_data['name'],
                created_by=request.user,
            )
            GroupMembership.objects.create(
                group=group,
                user=request.user,
                role=GroupMembership.Role.OWNER,
            )

        group = get_accessible_group_for_user(group.id, request.user)
        return Response(
            GroupSerializer(group, context={'user': request.user}).data,
            status=status.HTTP_201_CREATED,
        )


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

        ensure_owner_membership(group)
        membership, created = GroupMembership.objects.get_or_create(
            group=group,
            user=request.user,
            defaults={'role': GroupMembership.Role.MEMBER},
        )
        if not created and membership.role not in (
            GroupMembership.Role.MEMBER,
            GroupMembership.Role.OWNER,
        ):
            membership.role = GroupMembership.Role.MEMBER
            membership.save(update_fields=['role'])

        group = get_accessible_group_for_user(group.id, request.user)
        response = {
            'group': GroupSerializer(group, context={'user': request.user}).data,
            'joined': created,
        }
        return Response(
            response,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id):
        group = get_accessible_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_is_group_owner(group, request.user):
            return Response(
                {'detail': 'Only the trip owner can delete this trip.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group = get_accessible_group_for_user(group_id, request.user)
        if group is None:
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
                'group': GroupSerializer(group, context={'user': request.user}).data,
                'members': members_data,
            },
            status=status.HTTP_200_OK,
        )


class GroupMemberManageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id, user_id):
        group = get_accessible_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user_is_group_owner(group, request.user):
            return Response(
                {'detail': 'Only the trip owner can remove members.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.id == user_id:
            return Response(
                {'detail': 'Trip owners cannot remove themselves. Delete the trip instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_count, _ = GroupMembership.objects.filter(
            group=group,
            user_id=user_id,
        ).delete()
        if deleted_count == 0:
            return Response(
                {'detail': 'Member not found in this trip.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupLeaveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group = get_accessible_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        membership = GroupMembership.objects.filter(
            group=group,
            user=request.user,
        ).first()
        if membership is None:
            return Response(
                {'detail': 'You are not a member of this trip.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership.role == GroupMembership.Role.OWNER or group.created_by_id == request.user.id:
            return Response(
                {'detail': 'Trip owners cannot leave. Delete the trip instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WaypointView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group = get_accessible_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'Group not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CreateWaypointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        waypoint = group.waypoints.create(
            created_by=request.user,
            **serializer.validated_data,
        )
        return Response(WaypointSerializer(waypoint).data, status=status.HTTP_201_CREATED)


class GroupPlannerListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                'group': GroupSerializer(group, context={'user': request.user}).data,
                'categories': serialize_planner_tasks(group),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, group_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PlannerTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = group.planner_tasks.create(
            created_by=request.user,
            title=serializer.validated_data['title'],
            category=serializer.validated_data['category'],
            due_date=serializer.validated_data.get('due_date'),
            note=serializer.validated_data.get('note') or '',
            sort_order=serializer.validated_data.get('sort_order', 0),
        )
        task = get_planner_task_for_group(group, task.id)
        return Response(GroupPlannerTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class GroupPlannerTaskDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, group_id, task_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = get_planner_task_for_group(group, task_id)
        if task is None:
            return Response(
                {'detail': 'Planner task not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_owner = user_is_group_owner(group, request.user)
        is_creator = task.created_by_id == request.user.id
        if not is_owner and not is_creator:
            return Response(
                {'detail': 'Only the task creator or trip owner can edit this task.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PlannerTaskUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(task, field, '' if field == 'note' and value is None else value)
        task.save()
        return Response(GroupPlannerTaskSerializer(task).data, status=status.HTTP_200_OK)

    def delete(self, request, group_id, task_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = get_planner_task_for_group(group, task_id)
        if task is None:
            return Response(
                {'detail': 'Planner task not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_owner = user_is_group_owner(group, request.user)
        if not is_owner:
            if task.created_by_id != request.user.id:
                return Response(
                    {'detail': 'Only the task creator or trip owner can delete this task.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if task.status != GroupPlannerTask.Status.TODO:
                return Response(
                    {
                        'detail': (
                            'Members can delete only their own tasks that are still in todo.'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupPlannerTaskAssignView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, task_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = get_planner_task_for_group(group, task_id)
        if task is None:
            return Response(
                {'detail': 'Planner task not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PlannerTaskAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assigned_to_user_id = serializer.validated_data.get('assigned_to_user_id')

        is_owner = user_is_group_owner(group, request.user)
        if is_owner:
            if assigned_to_user_id is None:
                task.assigned_to = None
            else:
                membership = group.memberships.filter(user_id=assigned_to_user_id).first()
                if membership is None:
                    return Response(
                        {'detail': 'Assigned user must be a member of this group.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                task.assigned_to_id = assigned_to_user_id
            task.save(update_fields=['assigned_to', 'updated_at'])
            task = get_planner_task_for_group(group, task.id)
            return Response(GroupPlannerTaskSerializer(task).data, status=status.HTTP_200_OK)

        if assigned_to_user_id != request.user.id:
            return Response(
                {'detail': 'Members can only assign an unassigned task to themselves.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if task.assigned_to_id is not None:
            return Response(
                {'detail': 'Members cannot reassign tasks that already have an assignee.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task.assigned_to = request.user
        task.save(update_fields=['assigned_to', 'updated_at'])
        task = get_planner_task_for_group(group, task.id)
        return Response(GroupPlannerTaskSerializer(task).data, status=status.HTTP_200_OK)


class GroupPlannerTaskStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, task_id):
        group = get_planner_group_for_user(group_id, request.user)
        if group is None:
            return Response(
                {'detail': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = get_planner_task_for_group(group, task_id)
        if task is None:
            return Response(
                {'detail': 'Planner task not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PlannerTaskStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_owner = user_is_group_owner(group, request.user)
        if not is_owner:
            if task.assigned_to_id is None:
                return Response(
                    {'detail': 'Only the trip owner can update the status of an unassigned task.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if task.assigned_to_id != request.user.id:
                return Response(
                    {'detail': 'Members can only update status for tasks assigned to them.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        task.status = serializer.validated_data['status']
        task.save(update_fields=['status', 'updated_at'])
        return Response(GroupPlannerTaskSerializer(task).data, status=status.HTTP_200_OK)
