from rest_framework import serializers

from .models import MapRegion, Trail


class MapRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapRegion
        fields = ['id', 'name', 'bounding_box', 'size_mb', 'trail_count']


class TrailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trail
        fields = ['id', 'region', 'name', 'difficulty', 'elevation_gain_m', 'geojson']

