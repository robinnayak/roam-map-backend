from rest_framework.permissions import BasePermission

from .models import Group, GroupMembership


def is_group_member(user, group_id: int) -> bool:
    if Group.objects.filter(id=group_id, created_by=user).exists():
        return True
    return GroupMembership.objects.filter(group_id=group_id, user=user).exists()


def is_group_owner(user, group_id: int) -> bool:
    if Group.objects.filter(id=group_id, created_by=user).exists():
        return True
    return GroupMembership.objects.filter(
        group_id=group_id,
        user=user,
        role=GroupMembership.Role.OWNER,
    ).exists()


class IsGroupOwner(BasePermission):
    message = 'Only the trip owner can perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        group_id = view.kwargs.get('group_id')
        if group_id is None:
            return False

        # Let the view return a 404 for missing groups instead of masking it as a 403.
        if not Group.objects.filter(id=group_id).exists():
            return True

        return is_group_owner(request.user, group_id)

    def has_object_permission(self, request, view, obj):
        group_id = getattr(obj, 'group_id', None)
        if group_id is None:
            route = getattr(obj, 'route', None)
            group_id = getattr(route, 'group_id', None)
        if group_id is None:
            return False
        return is_group_owner(request.user, group_id)
