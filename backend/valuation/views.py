from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import time

from .tasks import add_numbers, hello_world, debug_sleep
from .forms import ValuationRequestForm
from .models import ValuationRequest


def health_check(request):
    """Basic health check endpoint"""
    return JsonResponse({"status": "ok", "timestamp": time.time()})


@method_decorator(csrf_exempt, name='dispatch')
class TestTaskView(View):
    """Endpoint for testing Celery tasks"""
    
    def get(self, request):
        """Get task status information"""
        return JsonResponse({
            "available_tasks": [
                "add_numbers",
                "hello_world", 
                "debug_sleep"
            ],
            "help": "POST to this endpoint to execute tasks"
        })
    
    def post(self, request):
        """Execute a Celery task asynchronously"""
        try:
            data = json.loads(request.body) if request.body else {}
            task_name = data.get('task', 'hello_world')
            
            # Execute task based on name
            if task_name == 'add_numbers':
                x = data.get('x', 5) 
                y = data.get('y', 3)
                result = add_numbers.delay(x, y)
                
                return JsonResponse({
                    "status": "task_started",
                    "task_name": task_name,
                    "task_id": result.id,
                    "params": {"x": x, "y": y},
                    "message": f"Task {task_name} started with params x={x}, y={y}"
                })
                
            elif task_name == 'debug_sleep':
                duration = data.get('duration', 10)
                result = debug_sleep.delay(duration)
                
                return JsonResponse({
                    "status": "task_started",
                    "task_name": task_name, 
                    "task_id": result.id,
                    "params": {"duration": duration},
                    "message": f"Long-running task started (sleep {duration}s)",
                    "note": "This task will not block other requests"
                })
                
            elif task_name == 'hello_world':
                result = hello_world.delay()
                
                return JsonResponse({
                    "status": "task_started", 
                    "task_name": task_name,
                    "task_id": result.id,
                    "message": "Hello world task started"
                })
                
            else:
                return JsonResponse({
                    "error": f"Unknown task: {task_name}",
                    "available_tasks": ["add_numbers", "hello_world", "debug_sleep"]
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


def manual_test_task_view(request):
    """Endpoint for manually triggering a test task without parameters"""
    
    result = debug_sleep.delay(20)  # Default sleep duration of 20 seconds
    return JsonResponse({
        "status": "task_started",
        "task_name": "debug_sleep",
        "task_id": result.id,
        "params": {"duration": 20},
        "message": "Manually triggered debug_sleep task with duration=20 seconds"
    })

def manual_sleep_test_view(request):
    """Endpoint for manually blocking the worker with a long-running task to check that only the worker is available
    (when we run the server with manage.py runserver).
    This will be also helpful once we implement K8S"""
    
    time.sleep(10)  # Simulate a long-running task that blocks the worker for 10 seconds
    
    return JsonResponse({
        "status": "completed",
        "message": f"Manually triggered debug_sleep task with duration=10 seconds"
    })


class ValuationFormView(View):
    """Handle property valuation form submission"""
    
    def get(self, request):
        """Render the valuation form"""
        form = ValuationRequestForm()
        return render(request, 'valuation/form.html', {'form': form})
    
    def post(self, request):
        """Process AJAX JSON form submission"""
        # Expect JSON content only
        if request.content_type != 'application/json':
            return JsonResponse({
                'success': False,
                'errors': {'__all__': ['JSON content type required']}
            }, status=400)
            
        try:
            data = json.loads(request.body)
            form = ValuationRequestForm(data)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'errors': {'__all__': ['Invalid JSON data']}
            }, status=400)
        
        if form.is_valid():
            # Save the valuation request
            valuation_request = form.save(commit=False)
            valuation_request.status = ValuationRequest.Status.PENDING
            valuation_request.save()
            
            # TODO: In future, launch Celery task here
            # celery_task = some_valuation_task.delay(valuation_request.id)
            # valuation_request.celery_task_id = celery_task.id
            # valuation_request.status = ValuationRequest.Status.PROCESSING
            # valuation_request.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Valuation request submitted successfully',
                'request_id': valuation_request.id,
                'status': valuation_request.status,
                # Future: 'task_id': valuation_request.celery_task_id
            })
        
        else:
            # Form has validation errors
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
