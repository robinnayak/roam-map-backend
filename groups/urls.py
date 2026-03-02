from django.urls import path

from .views import CreateGroupView, GroupMembersView, JoinGroupView, WaypointView

urlpatterns = [
    path('', CreateGroupView.as_view(), name='create-group'),
    path('join/', JoinGroupView.as_view(), name='join-group'),
    path('<int:group_id>/members/', GroupMembersView.as_view(), name='group-members'),
    path('<int:group_id>/waypoints/', WaypointView.as_view(), name='create-waypoint'),
]
