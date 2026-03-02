import uuid

from django.conf import settings
from django.db import models


def generate_invite_code() -> str:
    return uuid.uuid4().hex[:10]


class Group(models.Model):
    name = models.CharField(max_length=255)
    invite_code = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        default=generate_invite_code,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['group', 'user'], name='unique_group_membership')
        ]
        indexes = [
            models.Index(fields=['group', 'user']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f'{self.user_id} in {self.group_id}'


class Waypoint(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='waypoints',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_waypoints',
    )
    label = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'created_at']),
        ]

    def __str__(self):
        return f'{self.label} ({self.group_id})'
