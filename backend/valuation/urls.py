from django.urls import path
from .views import health_check, TestTaskView, manual_test_task_view, manual_sleep_test_view

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("test-task/", TestTaskView.as_view(), name="test_task"),
    path("manual-test-task/", manual_test_task_view, name="manual_test"),  # For manual running of asynctasks
    path("manual-sleep-task/", manual_sleep_test_view, name="manual_sleep_test"),  # For manual testing debug_sleep to block the worker and verify async behavior
]