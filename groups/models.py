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
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        MEMBER = 'member', 'Member'

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
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
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
        return f'{self.user_id} in {self.group_id} ({self.role})'


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


class GroupPlannerTask(models.Model):
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='planner_tasks',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_group_planner_tasks',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_group_planner_tasks',
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.TODO,
    )
    due_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'sort_order', 'created_at', 'id']
        indexes = [
            models.Index(fields=['group', 'category', 'sort_order', 'created_at']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'assigned_to']),
        ]

    def __str__(self):
        return f'{self.title} ({self.group_id})'
