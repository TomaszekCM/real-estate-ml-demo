from celery import shared_task


@shared_task
def hello_world():
    """
    Basic hello world task for Celery testing
    """
    return "Hello from Celery!"
