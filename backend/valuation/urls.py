from django.urls import path
from .views import (
    health_check, TestTaskView, manual_test_task_view, 
    manual_sleep_test_view, ValuationFormView, ValuationStatusView
)

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("test-task/", TestTaskView.as_view(), name="test_task"),
    path("manual-test-task/", manual_test_task_view, name="manual_test"),
    path("manual-sleep-task/", manual_sleep_test_view, name="manual_sleep_test"),
    path("valuation/", ValuationFormView.as_view(), name="valuation_form"),
    path("valuation/<int:request_id>/status/", ValuationStatusView.as_view(), name="valuation_status"),
]