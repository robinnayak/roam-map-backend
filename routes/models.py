from django.conf import settings
from django.db import models

from groups.models import Group


class MapRegion(models.Model):
    name = models.CharField(max_length=255)
    bounding_box = models.JSONField()
    size_mb = models.DecimalField(max_digits=8, decimal_places=2)
    trail_count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


class Trail(models.Model):
    region = models.ForeignKey(
        MapRegion,
        on_delete=models.CASCADE,
        related_name='trails',
    )
    name = models.CharField(max_length=255)
    difficulty = models.CharField(max_length=50)
    elevation_gain_m = models.PositiveIntegerField()
    geojson = models.JSONField()

    class Meta:
        indexes = [
            models.Index(fields=['region']),
            models.Index(fields=['difficulty']),
        ]

    def __str__(self):
        return self.name


class UserRoute(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = 'outbound', 'Outbound'
        RETURN = 'return', 'Return'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MODERATE = 'moderate', 'Moderate'
        HARD = 'hard', 'Hard'
        TECHNICAL = 'technical', 'Technical'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        ARCHIVED = 'archived', 'Archived'

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='routes',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_routes',
    )
    trail = models.ForeignKey(
        Trail,
        on_delete=models.SET_NULL,
        related_name='user_routes',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=120)
    direction = models.CharField(max_length=16, choices=Direction.choices)
    difficulty = models.CharField(max_length=16, choices=Difficulty.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    total_distance_km = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['created_by']),
            models.Index(fields=['trail']),
        ]
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return self.title


class RouteWaypoint(models.Model):
    class WaypointType(models.TextChoices):
        CAMPSITE = 'campsite', 'Campsite'
        TEAHOUSE = 'teahouse', 'Teahouse'
        CHECKPOINT = 'checkpoint', 'Checkpoint'
        REST_STOP = 'rest_stop', 'Rest Stop'
        EMERGENCY_POINT = 'emergency_point', 'Emergency Point'
        TRAILHEAD = 'trailhead', 'Trailhead'

    route = models.ForeignKey(
        UserRoute,
        on_delete=models.CASCADE,
        related_name='waypoints',
    )
    name = models.CharField(max_length=120)
    latitude = models.FloatField()
    longitude = models.FloatField()
    elevation_m = models.FloatField(null=True, blank=True)
    day_number = models.PositiveIntegerField(null=True, blank=True)
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)
    order = models.PositiveIntegerField()
    waypoint_type = models.CharField(max_length=24, choices=WaypointType.choices)
    is_completed = models.BooleanField(default=False)
    is_emergency_point = models.BooleanField(default=False)
    estimated_duration_from_prev = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['day_number', 'order', 'id']
        indexes = [
            models.Index(fields=['route', 'day_number', 'order']),
            models.Index(fields=['waypoint_type']),
        ]

    def __str__(self):
        return f'{self.name} ({self.route_id})'
