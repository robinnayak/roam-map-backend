from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class UserLocation(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='location',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.FloatField(null=True, blank=True)
    is_sharing_live = models.BooleanField(default=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} @ {self.latitude}, {self.longitude}'


class UserConnection(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        BLOCKED = 'blocked', 'Blocked'

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_connections',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_connections',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user'],
                name='unique_user_connection_direction',
            ),
            models.CheckConstraint(
                check=~models.Q(from_user=models.F('to_user')),
                name='prevent_self_user_connection',
            ),
        ]
        indexes = [
            models.Index(fields=['from_user', 'status']),
            models.Index(fields=['to_user', 'status']),
        ]

    def __str__(self):
        return f'{self.from_user_id} -> {self.to_user_id} ({self.status})'


def get_connection_lookup(user_a_id, user_b_id):
    return Q(from_user_id=user_a_id, to_user_id=user_b_id) | Q(
        from_user_id=user_b_id,
        to_user_id=user_a_id,
    )


def get_connected_user_ids(user_id):
    accepted_connections = UserConnection.objects.filter(
        status=UserConnection.Status.ACCEPTED,
    ).filter(
        Q(from_user_id=user_id) | Q(to_user_id=user_id)
    )
    connected_user_ids = {user_id}
    for connection in accepted_connections:
        if connection.from_user_id == user_id:
            connected_user_ids.add(connection.to_user_id)
        else:
            connected_user_ids.add(connection.from_user_id)
    return connected_user_ids
