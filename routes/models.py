from django.db import models


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
