from django.urls import path

from .views import (
    ChecklistItemDetailView,
    ChecklistListCreateView,
    ChecklistResetView,
    ChecklistSeedView,
)


urlpatterns = [
    path('', ChecklistListCreateView.as_view(), name='checklist-list'),
    path('seed/', ChecklistSeedView.as_view(), name='checklist-seed'),
    path('reset/', ChecklistResetView.as_view(), name='checklist-reset'),
    path('<int:item_id>/', ChecklistItemDetailView.as_view(), name='checklist-item-detail'),
]

