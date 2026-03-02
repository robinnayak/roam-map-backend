from django.core.cache import cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MapRegion, Trail
from .serializers import MapRegionSerializer, TrailSerializer


class MapRegionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        regions = MapRegion.objects.all().order_by('name')
        serializer = MapRegionSerializer(regions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TrailGeoJSONView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, region_id):
        if not MapRegion.objects.filter(id=region_id).exists():
            return Response({'detail': 'Region not found.'}, status=status.HTTP_404_NOT_FOUND)

        trails = Trail.objects.filter(region_id=region_id).order_by('name')
        features = [
            {
                'type': 'Feature',
                'id': trail.id,
                'geometry': trail.geojson,
                'properties': {
                    'trail_id': trail.id,
                    'name': trail.name,
                    'difficulty': trail.difficulty,
                    'elevation_gain_m': trail.elevation_gain_m,
                    'region_id': trail.region_id,
                },
            }
            for trail in trails
        ]
        payload = {
            'type': 'FeatureCollection',
            'features': features,
        }
        return Response(payload, status=status.HTTP_200_OK)


class TrailDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, trail_id):
        try:
            trail = Trail.objects.select_related('region').get(id=trail_id)
        except Trail.DoesNotExist:
            return Response({'detail': 'Trail not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TrailSerializer(trail)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RegionWeatherView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    CACHE_TTL_SECONDS = 3600

    def get(self, request, region_id):
        try:
            region = MapRegion.objects.get(id=region_id)
        except MapRegion.DoesNotExist:
            return Response({'detail': 'Region not found.'}, status=status.HTTP_404_NOT_FOUND)

        cache_key = f'region_weather:{region_id}'
        cached_payload = cache.get(cache_key)
        if cached_payload:
            return Response(cached_payload, status=status.HTTP_200_OK)

        payload = {
            'region_id': region.id,
            'region_name': region.name,
            'forecast': [],
            'source': 'placeholder',
            'note': 'Weather provider integration pending. Response is cached for 1 hour.',
        }
        cache.set(cache_key, payload, self.CACHE_TTL_SECONDS)
        return Response(payload, status=status.HTTP_200_OK)
