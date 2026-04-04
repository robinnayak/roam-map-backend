from django.urls import path

from .views import (
    GroupRouteDetailView,
    GroupRouteListCreateView,
    RouteWaypointDetailView,
    RouteWaypointListCreateView,
    RouteWaypointReorderView,
)

urlpatterns = [
    path('groups/<int:group_id>/routes/', GroupRouteListCreateView.as_view(), name='group-routes'),
    path(
        'groups/<int:group_id>/routes/<int:route_id>/',
        GroupRouteDetailView.as_view(),
        name='group-route-detail',
    ),
    path(
        'groups/<int:group_id>/routes/<int:route_id>/waypoints/',
        RouteWaypointListCreateView.as_view(),
        name='route-waypoints',
    ),
    path(
        'groups/<int:group_id>/routes/<int:route_id>/waypoints/<int:wp_id>/',
        RouteWaypointDetailView.as_view(),
        name='route-waypoint-detail',
    ),
    path(
        'groups/<int:group_id>/routes/<int:route_id>/waypoints/reorder/',
        RouteWaypointReorderView.as_view(),
        name='route-waypoint-reorder',
    ),
]
