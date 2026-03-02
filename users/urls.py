from django.urls import path

from .views import GroupLocationsView, UpdateLocationView

urlpatterns = [
    path('location/', UpdateLocationView.as_view(), name='update-location'),
    path('location/group/<int:group_id>/', GroupLocationsView.as_view(), name='group-locations'),
]
