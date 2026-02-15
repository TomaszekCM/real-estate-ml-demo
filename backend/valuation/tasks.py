from celery import shared_task
import time
import logging


logger = logging.getLogger(__name__)


@shared_task
def add_numbers(x, y):
    """
    Simple task for testing Celery functionality
    """
    logger.info(f"Starting add_numbers task: {x} + {y}")
    # Simulate some processing time
    time.sleep(1) 
    result = x + y
    logger.info(f"Completed add_numbers task: {result}")
    return result


@shared_task
def hello_world():
    """
    Basic hello world task for Celery testing
    """
    logger.info("Starting hello_world task")
    result = "Hello from Celery!"
    logger.info("Completed hello_world task")
    return result


@shared_task
def debug_sleep(duration=10):
    """
    Task with configurable sleep duration for testing async behavior
    This task helps test that multiple long-running tasks don't block each other
    """
    task_id = debug_sleep.request.id
    logger.info(f"Starting debug_sleep task {task_id} for {duration} seconds")
    
    start_time = time.time()
    time.sleep(duration)
    end_time = time.time()
    
    actual_duration = round(end_time - start_time, 2)
    result = {
        'task_id': task_id,
        'requested_duration': duration,
        'actual_duration': actual_duration,
        'message': f'Slept for {actual_duration} seconds'
    }
    
    logger.info(f"Completed debug_sleep task {task_id} after {actual_duration} seconds")
    return result
