from django.urls import path

from .views import MapRegionListView, RegionWeatherView, TrailDetailView, TrailGeoJSONView

urlpatterns = [
    path('regions/', MapRegionListView.as_view(), name='routes-regions-list'),
    path('trails/<int:region_id>/', TrailGeoJSONView.as_view(), name='routes-trails-geojson'),
    path('trails/detail/<int:trail_id>/', TrailDetailView.as_view(), name='routes-trail-detail'),
    path('weather/<int:region_id>/', RegionWeatherView.as_view(), name='routes-region-weather'),
]

