from django.urls import path

from .views import (
    ConnectionAcceptView,
    ConnectionDeclineView,
    ConnectionListView,
    ConnectionRequestView,
    PendingConnectionListView,
)

urlpatterns = [
    path('', ConnectionListView.as_view(), name='connection-list'),
    path('request/', ConnectionRequestView.as_view(), name='connection-request'),
    path('pending/', PendingConnectionListView.as_view(), name='connection-pending'),
    path('<int:connection_id>/accept/', ConnectionAcceptView.as_view(), name='connection-accept'),
    path('<int:connection_id>/decline/', ConnectionDeclineView.as_view(), name='connection-decline'),
]
