from django.urls import path

from .views import (
    GroupDetailView,
    GroupLeaveView,
    GroupListCreateView,
    GroupMemberManageView,
    GroupMembersView,
    GroupPlannerListCreateView,
    GroupPlannerTaskAssignView,
    GroupPlannerTaskDetailView,
    GroupPlannerTaskStatusView,
    JoinGroupView,
    WaypointView,
)

urlpatterns = [
    path('', GroupListCreateView.as_view(), name='list-create-group'),
    path('join/', JoinGroupView.as_view(), name='join-group'),
    path('<int:group_id>/', GroupDetailView.as_view(), name='group-detail'),
    path('<int:group_id>/leave/', GroupLeaveView.as_view(), name='leave-group'),
    path('<int:group_id>/members/', GroupMembersView.as_view(), name='group-members'),
    path(
        '<int:group_id>/members/<int:user_id>/',
        GroupMemberManageView.as_view(),
        name='group-member-manage',
    ),
    path(
        '<int:group_id>/planner/',
        GroupPlannerListCreateView.as_view(),
        name='group-planner-list-create',
    ),
    path(
        '<int:group_id>/planner/<int:task_id>/',
        GroupPlannerTaskDetailView.as_view(),
        name='group-planner-task-detail',
    ),
    path(
        '<int:group_id>/planner/<int:task_id>/assign/',
        GroupPlannerTaskAssignView.as_view(),
        name='group-planner-task-assign',
    ),
    path(
        '<int:group_id>/planner/<int:task_id>/status/',
        GroupPlannerTaskStatusView.as_view(),
        name='group-planner-task-status',
    ),
    path('<int:group_id>/waypoints/', WaypointView.as_view(), name='create-waypoint'),
]
