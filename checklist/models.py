from django.conf import settings
from django.db import models


class PackingItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='packing_items',
    )
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=64)
    is_checked = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=1)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'sort_order', 'id']
        indexes = [
            models.Index(fields=['user', 'category', 'sort_order']),
            models.Index(fields=['user', 'is_checked']),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.category}:{self.name}'

