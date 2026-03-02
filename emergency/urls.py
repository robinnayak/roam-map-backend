from django.urls import path

from .views import ResolveSOSView, TriggerSOSView

urlpatterns = [
    path('sos/', TriggerSOSView.as_view(), name='trigger-sos'),
    path('sos/<int:alert_id>/resolve/', ResolveSOSView.as_view(), name='resolve-sos'),
]
