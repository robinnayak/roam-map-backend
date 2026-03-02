from django.conf import settings
from django.db import models
from django.utils import timezone


class SOSAlert(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sos_alerts',
    )
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='sos_alerts',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    triggered_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['triggered_at']),
        ]

    def __str__(self):
        return f'SOSAlert<{self.id}> user={self.user_id} group={self.group_id} active={self.is_active}'
