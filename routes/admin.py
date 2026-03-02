from django.contrib import admin

from .models import MapRegion, Trail


@admin.register(MapRegion)
class MapRegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'size_mb', 'trail_count')
    search_fields = ('name',)


@admin.register(Trail)
class TrailAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'difficulty', 'elevation_gain_m')
    search_fields = ('name', 'region__name', 'difficulty')
    list_filter = ('difficulty', 'region')
    list_select_related = ('region',)
