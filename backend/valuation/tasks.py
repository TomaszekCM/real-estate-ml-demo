from celery import shared_task
import time
import logging
import requests
from django.conf import settings
from .models import ValuationRequest, ValuationResult


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


@shared_task
def process_valuation_request(request_id):
    """
    Asynchronous task to process valuation request using ML service
    
    Workflow:
    1. Update status to PROCESSING  
    2. Call ML service /predict endpoint
    3. Create ValuationResult on success
    4. Update status to DONE/FAILED
    """
    
    task_id = process_valuation_request.request.id
    logger.info(f"Starting valuation task {task_id} for request ID: {request_id}")
    
    try:
        # Get the valuation request
        valuation_request = ValuationRequest.objects.get(id=request_id)
        logger.info(f"Processing valuation for {valuation_request.city}, {valuation_request.area_sqm}m²")
        
        # Step 1: Update status to PROCESSING (with UX delay)
        time.sleep(2)  # Simulate initial processing delay for better UX
        valuation_request.status = ValuationRequest.Status.PROCESSING
        valuation_request.save()
        logger.info(f"Request {request_id} status updated to PROCESSING")
        
        # Step 2: Prepare data for ML service
        ml_data = {
            "city": valuation_request.city,
            "district": valuation_request.district or "Unknown",  # Handle nullable district
            "area_sqm": float(valuation_request.area_sqm),
            "rooms": valuation_request.rooms
        }
        
        # Step 3: Call ML service predict endpoint
        ml_service_url = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')
        predict_endpoint = getattr(settings, 'ML_SERVICE_PREDICT_ENDPOINT', '/predict')
        timeout = getattr(settings, 'ML_SERVICE_TIMEOUT', 30)
        
        ml_url = f"{ml_service_url}{predict_endpoint}"
        logger.info(f"Calling ML service: {ml_url} with data: {ml_data}")
        
        # Make request to ML service
        response = requests.post(
            ml_url,
            json=ml_data,
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"ML service returned status {response.status_code}: {response.text}")
            
        ml_result = response.json()
        logger.info(f"ML service response: {ml_result}")
        
        # Step 4: Additional processing delay for UX (simulate complex calculations)
        time.sleep(2)  # Brief delay before saving results
        
        # Step 5: Create ValuationResult
        estimated_price = int(ml_result.get('predicted_price', 0))
        area_sqm = float(valuation_request.area_sqm)
        price_per_sqm = int(estimated_price / area_sqm) if area_sqm > 0 else 0
        
        ValuationResult.objects.create(
            request=valuation_request,
            estimated_price=estimated_price,
            price_per_sqm=price_per_sqm,
            model_version=ml_result.get('model_version', 'v1.0')
        )
        
        # Step 6: Update status to DONE
        valuation_request.status = ValuationRequest.Status.DONE
        valuation_request.save()
        
        logger.info(f"Valuation completed successfully for request {request_id}. "
                   f"Estimated price: {estimated_price}")
        
        return {
            'status': 'success',
            'request_id': request_id,
            'estimated_price': estimated_price,
            'price_per_sqm': price_per_sqm,
            'model_version': ml_result.get('model_version', 'v1.0'),
            'task_id': task_id
        }
        
    except ValuationRequest.DoesNotExist:
        error_msg = f"ValuationRequest {request_id} not found"
        logger.error(error_msg)
        return {'status': 'error', 'error': error_msg}
        
    except requests.exceptions.RequestException as e:
        error_msg = f"ML service communication error: {str(e)}"
        logger.error(error_msg)
        
        # Update status to FAILED
        try:
            valuation_request.status = ValuationRequest.Status.FAILED
            valuation_request.save()
        except:
            pass
            
        return {'status': 'error', 'error': error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error during valuation: {str(e)}"
        logger.error(error_msg)
        
        # Update status to FAILED
        try:
            valuation_request.status = ValuationRequest.Status.FAILED
            valuation_request.save()
        except:
            pass
            
        return {'status': 'error', 'error': error_msg}
