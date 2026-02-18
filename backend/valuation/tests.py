from django.test import TestCase
from django.core.cache import cache
from django.db import connection
import redis
from django.conf import settings
from .models import ValuationRequest, ValuationResult
from celery.result import AsyncResult
from unittest.mock import patch, Mock
import requests
from .tasks import process_valuation_request
from django.core.exceptions import ValidationError
from .forms import ValuationRequestForm
from django import forms


class RedisCacheTest(TestCase):
    """Test Redis cache functionality"""

    def setUp(self):
        """Clear cache before each test"""
        cache.clear()

    def test_redis_connection_config(self):
        """Test Redis connection configuration"""
        # Check if cache backend is configured correctly  
        cache_config = settings.CACHES['default']
        self.assertEqual(cache_config['BACKEND'], 'django.core.cache.backends.redis.RedisCache')
        
        # Check if we can connect to Redis directly
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=0)
            redis_client.ping()
            redis_connection_works = True
        except (redis.ConnectionError, ConnectionRefusedError):
            redis_connection_works = False
            
        self.assertTrue(redis_connection_works, "Direct Redis connection failed")

    def test_cache_key_prefix(self):
        """Test that cache keys have the correct prefix"""
        cache.set('prefixed_key', 'value')
        
        # Direct Redis connection to check actual key
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        keys = redis_client.keys('*prefixed_key*')
        
        # Should find key with prefix
        self.assertTrue(len(keys) > 0)
        # Key should contain our prefix from settings
        key_found = any(b'real_estate' in key for key in keys)
        self.assertTrue(key_found, "Cache key prefix not found")

    def test_redis_basic_operations(self):
        """Test basic Redis set/get operations"""
        # Test setting and getting data
        cache.set('test_key', 'test_value', timeout=60)
        result = cache.get('test_key')
        
        self.assertEqual(result, 'test_value')
        
        # Test with complex data
        test_data = {
            'city': 'Warsaw',
            'area_sqm': 75.5,
            'rooms': 3,
            'estimated_price': 850000
        }
        cache.set('property_data', test_data, timeout=300)
        cached_data = cache.get('property_data')
        
        self.assertEqual(cached_data, test_data)

    def test_redis_timeout(self):
        """Test that Redis respects timeout settings"""
        import time
        
        # Set with very short timeout
        cache.set('short_lived', 'temporary_value', timeout=1)
        
        # Should exist immediately
        self.assertEqual(cache.get('short_lived'), 'temporary_value')
        
        # Wait and check it's gone
        time.sleep(2)
        self.assertIsNone(cache.get('short_lived'))

    def test_redis_delete(self):
        """Test deleting items from cache"""
        cache.set('to_delete', 'delete_me')
        self.assertEqual(cache.get('to_delete'), 'delete_me')
        
        cache.delete('to_delete')
        self.assertIsNone(cache.get('to_delete'))


class DatabaseConnectionTest(TestCase):
    """Test PostgreSQL database connectivity"""
    
    def test_database_connection(self):
        """Test that PostgreSQL connection works"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
        self.assertEqual(result[0], 1)
        
    def test_database_engine(self):
        """Test that PostgreSQL is configured correctly"""
        db_engine = connection.settings_dict['ENGINE']
        self.assertEqual(db_engine, 'django.db.backends.postgresql')


class InfrastructureHealthTest(TestCase):
    """Integration test for all infrastructure components"""
    
    def test_full_infrastructure_health(self):
        """Test that Redis + PostgreSQL + Django work together"""
        
        # 1. Test database by creating a model instance
        request = ValuationRequest.objects.create(
            city='Warsaw',
            district='Mokotów',
            area_sqm=75.5,
            rooms=3
        )
        self.assertIsNotNone(request.pk)
        
        # 2. Test cache by storing the request data
        cache_key = f'valuation_request_{request.pk}'
        request_data = {
            'city': request.city,
            'area_sqm': request.area_sqm,
            'rooms': request.rooms
        }
        cache.set(cache_key, request_data, timeout=300)
        
        # 3. Verify cache retrieval
        cached_data = cache.get(cache_key)
        self.assertEqual(cached_data['city'], 'Warsaw')
        self.assertEqual(cached_data['area_sqm'], 75.5)
        
        # 4. Clean up
        cache.delete(cache_key)
        request.delete()


class CeleryTaskTest(TestCase):
    """Test Celery task functionality"""

    def test_celery_app_configuration(self):
        """Test that Celery is properly configured"""
        from valuation_api.celery import app as celery_app
        
        # Check if app can be imported
        self.assertIsNotNone(celery_app)
        self.assertEqual(celery_app.main, 'valuation_api')

    def test_hello_world_task_import(self):
        """Test that we can import our custom tasks without errors"""
        try:
            from .tasks import hello_world
            task_import_success = True
        except ImportError:
            task_import_success = False
        
        self.assertTrue(task_import_success, "Failed to import Celery task")

    def test_hello_world_task_sync(self):
        """Test hello_world task execution (synchronous mode for testing)"""  
        from .tasks import hello_world
        
        # Test task directly (not async)
        result = hello_world()
        self.assertEqual(result, "Hello from Celery!")

    def test_task_registration(self):
        """Test that tasks are properly registered with Celery"""
        from valuation_api.celery import app as celery_app
        
        # Check if our tasks are registered
        registered_tasks = list(celery_app.tasks.keys())
        
        # Define expected tasks to avoid duplication with endpoint test
        expected_tasks = [
            'valuation.tasks.add_numbers',
            'valuation.tasks.hello_world', 
            'valuation.tasks.debug_sleep'
        ]
        
        for task in expected_tasks:
            self.assertIn(task, registered_tasks)


class TaskEndpointTest(TestCase):
    """Test task execution endpoints"""
    
    def test_health_check_endpoint(self):
        """Test health check endpoint works"""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)
    
    def test_test_task_get_endpoint(self):
        """Test GET on test-task endpoint returns available tasks"""
        response = self.client.get('/api/test-task/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('available_tasks', data)
        self.assertIn('add_numbers', data['available_tasks'])
        self.assertIn('hello_world', data['available_tasks'])
        self.assertIn('debug_sleep', data['available_tasks'])
    
    def test_hello_world_task_endpoint(self):
        """Test POST to execute hello_world task"""
        response = self.client.post(
            '/api/test-task/',
            data='{"task": "hello_world"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'task_started')
        self.assertEqual(data['task_name'], 'hello_world')
        self.assertIn('task_id', data)
        
        # Verify task actually executes by checking result
        task_result = AsyncResult(data['task_id'])
        
        # Wait for task completion (with timeout)
        try:
            result = task_result.get(timeout=5)
            self.assertEqual(result, "Hello from Celery!")
        except Exception as e:
            self.fail(f"Task execution failed or timed out: {e}")
    
    def test_add_numbers_task_endpoint(self):
        """Test POST to execute add_numbers task with parameters"""
        response = self.client.post(
            '/api/test-task/',
            data='{"task": "add_numbers", "x": 15, "y": 25}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'task_started')
        self.assertEqual(data['task_name'], 'add_numbers')
        self.assertEqual(data['params']['x'], 15)
        self.assertEqual(data['params']['y'], 25)
        self.assertIn('task_id', data)
        
        # Verify task actually executes with correct calculation
        task_result = AsyncResult(data['task_id'])
        
        # Wait for task completion and verify calculation
        try:
            result = task_result.get(timeout=5)
            self.assertEqual(result, 40, "Task should calculate 15 + 25 = 40")
        except Exception as e:
            self.fail(f"Task execution failed or timed out: {e}")
    
    def test_debug_sleep_task_endpoint(self):
        """Test POST to execute debug_sleep task"""
        response = self.client.post(
            '/api/test-task/',
            data='{"task": "debug_sleep", "duration": 1}',  # Short duration for testing
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'task_started')
        self.assertEqual(data['task_name'], 'debug_sleep') 
        self.assertEqual(data['params']['duration'], 1)
        self.assertIn('note', data)  # Should mention non-blocking behavior
        self.assertIn('task_id', data)
        
        # Verify task actually executes and returns correct structure
        task_result = AsyncResult(data['task_id'])
        
        # Wait for task completion and verify result structure
        try:
            result = task_result.get(timeout=5)
            self.assertIn('task_id', result)
            self.assertIn('requested_duration', result)
            self.assertIn('actual_duration', result)
            self.assertIn('message', result)
            self.assertEqual(result['requested_duration'], 1)
            # Actual duration should be close to 1 second (within reasonable margin)
            self.assertGreaterEqual(result['actual_duration'], 0.9)
            self.assertLessEqual(result['actual_duration'], 1.5)
        except Exception as e:
            self.fail(f"Task execution failed or timed out: {e}")
    
    def test_invalid_task_name(self):
        """Test POST with invalid task name returns error"""
        response = self.client.post(
            '/api/test-task/',
            data='{"task": "nonexistent_task"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('available_tasks', data)


class AsyncTaskBehaviorTest(TestCase):
    """Test actual async task execution behavior"""
    
    def test_debug_sleep_task_execution(self):
        """Test debug_sleep task executes with correct timing"""
        from .tasks import debug_sleep
        import time
        
        # Test short duration to avoid slow tests
        start_time = time.time()
        result = debug_sleep(duration=1)  # Synchronous call for testing
        end_time = time.time()
        
        # Should take approximately 1 second
        actual_duration = end_time - start_time
        self.assertGreaterEqual(actual_duration, 0.9)
        self.assertLessEqual(actual_duration, 1.5)
        
        # Check result structure  
        self.assertIn('requested_duration', result)
        self.assertIn('actual_duration', result)
        self.assertIn('message', result)
        self.assertEqual(result['requested_duration'], 1)


class ValuationFormViewTest(TestCase):
    """Test property valuation form functionality"""

    def test_get_form_renders_correctly(self):
        """Test GET request returns form page"""
        response = self.client.get('/api/valuation/')
        
        # Should return 200 OK
        self.assertEqual(response.status_code, 200)
        
        # Should contain form elements
        self.assertContains(response, 'id="valuation-form"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'Property Valuation Request')
        
        # Should load our JavaScript file
        self.assertContains(response, 'valuation-form.js')

    def test_post_valid_json_creates_record(self):
        """Test POST with valid JSON data creates ValuationRequest"""
        valid_data = {
            'city': 'Warsaw',
            'district': 'Mokotow', 
            'area_sqm': 65.5,
            'rooms': 2
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=valid_data,
            content_type='application/json'
        )
        
        # Should return 200 with success JSON
        self.assertEqual(response.status_code, 200)
        
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['message'], 'Valuation request submitted successfully')
        self.assertIn('request_id', response_data)
        self.assertEqual(response_data['status'], 'PENDING')
        
        # Should create record in database
        self.assertEqual(ValuationRequest.objects.count(), 1)
        
        saved_request = ValuationRequest.objects.first()
        self.assertEqual(saved_request.city, 'Warsaw')
        self.assertEqual(saved_request.district, 'Mokotow')
        self.assertEqual(float(saved_request.area_sqm), 65.5)
        self.assertEqual(saved_request.rooms, 2)
        self.assertEqual(saved_request.status, ValuationRequest.Status.PENDING)

    def test_post_invalid_json_returns_errors(self):
        """Test POST with invalid data returns validation errors"""
        invalid_data = {
            'city': '',  # Required field empty
            'area_sqm': 15000,  # Too large (max 10000)
            'rooms': 25  # Too many (max 20)
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=invalid_data,
            content_type='application/json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        response_data = response.json()
        self.assertFalse(response_data['success'])
        self.assertIn('errors', response_data)
        
        errors = response_data['errors']
        self.assertIn('city', errors)  # Required field
        self.assertIn('area_sqm', errors)  # Max value validation
        self.assertIn('rooms', errors)  # Max value validation
        
        # Should NOT create record in database
        self.assertEqual(ValuationRequest.objects.count(), 0)

    def test_post_non_json_content_type_rejected(self):
        """Test POST with non-JSON content type is rejected"""
        form_data = {
            'city': 'Warsaw',
            'area_sqm': '65.5',
            'rooms': '2'
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=form_data,  # Form-encoded, not JSON
            content_type='application/x-www-form-urlencoded'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        response_data = response.json()
        self.assertFalse(response_data['success'])
        self.assertIn('JSON content type required', 
                     response_data['errors']['__all__'][0])
        
        # Should NOT create record in database
        self.assertEqual(ValuationRequest.objects.count(), 0)

    def test_post_malformed_json_returns_error(self):
        """Test POST with malformed JSON returns error"""
        response = self.client.post(
            '/api/valuation/',
            data='{"city":"Warsaw","area_sqm":}',  # Malformed JSON
            content_type='application/json'
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        response_data = response.json()
        self.assertFalse(response_data['success'])
        self.assertIn('Invalid JSON data', 
                     response_data['errors']['__all__'][0])

    def test_boundary_values_validation(self):
        """Test boundary values for area_sqm and rooms"""
        # Test minimum valid values
        min_valid_data = {
            'city': 'TestCity',
            'area_sqm': 10.0,  # Min allowed
            'rooms': 1  # Min allowed
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=min_valid_data,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Test maximum valid values
        max_valid_data = {
            'city': 'TestCity2',
            'area_sqm': 10000.0,  # Max allowed
            'rooms': 20  # Max allowed
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=max_valid_data,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Should have created 2 records
        self.assertEqual(ValuationRequest.objects.count(), 2)


# ==============================================================================
# ASYNC VALUATION PROCESSING TESTS
# ==============================================================================


class ProcessValuationTaskTest(TestCase):
    """Test async valuation processing Celery task"""

    def setUp(self):
        """Create test valuation request"""
        self.test_request = ValuationRequest.objects.create(
            city="Krakow",
            district="Stare Miasto",
            area_sqm=75.0,
            rooms=3,
            status=ValuationRequest.Status.PENDING
        )

    @patch('valuation.tasks.requests.post')
    def test_successful_valuation_processing(self, mock_post):
        """Test complete successful valuation workflow"""
        # Mock ML service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'predicted_price': 850000.0,
            'input_data': {
                'city': 'Krakow',
                'district': 'Stare Miasto', 
                'area_sqm': 75.0,
                'rooms': 3
            }
        }
        mock_post.return_value = mock_response

        # Execute task synchronously for testing
        with patch('valuation.tasks.time.sleep'):  # Skip sleep delays
            result = process_valuation_request(self.test_request.id)

        # Verify task result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['request_id'], self.test_request.id)
        self.assertEqual(result['estimated_price'], 850000)
        self.assertEqual(result['price_per_sqm'], 11333)  # 850000 / 75

        # Verify database updates
        self.test_request.refresh_from_db()
        self.assertEqual(self.test_request.status, ValuationRequest.Status.DONE)
        
        # Verify ValuationResult created
        results = ValuationResult.objects.filter(request=self.test_request)
        self.assertEqual(results.count(), 1)
        
        result_obj = results.first()
        self.assertEqual(result_obj.estimated_price, 850000)
        self.assertEqual(result_obj.price_per_sqm, 11333)
        self.assertEqual(result_obj.model_version, 'v1.0')

        # Verify ML service was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json'], {
            'city': 'Krakow',
            'district': 'Stare Miasto',
            'area_sqm': 75.0,
            'rooms': 3
        })

    @patch('valuation.tasks.requests.post')  
    def test_ml_service_error_handling(self, mock_post):
        """Test handling of ML service errors"""
        # Mock ML service error response
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.text = '{"detail":"Validation error"}'
        mock_post.return_value = mock_response

        # Execute task
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(self.test_request.id)

        # Verify error handling
        self.assertEqual(result['status'], 'error')
        self.assertIn('ML service returned status 422', result['error'])

        # Verify status updated to FAILED
        self.test_request.refresh_from_db()
        self.assertEqual(self.test_request.status, ValuationRequest.Status.FAILED)

        # No ValuationResult should be created
        self.assertEqual(ValuationResult.objects.filter(request=self.test_request).count(), 0)

    @patch('valuation.tasks.requests.post')
    def test_ml_service_timeout_handling(self, mock_post):
        """Test handling of ML service timeout"""
        # Mock timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Request timeout")

        # Execute task
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(self.test_request.id)

        # Verify error handling
        self.assertEqual(result['status'], 'error')
        self.assertIn('ML service communication error', result['error'])
        self.assertIn('Request timeout', result['error'])

        # Verify status updated to FAILED
        self.test_request.refresh_from_db()
        self.assertEqual(self.test_request.status, ValuationRequest.Status.FAILED)

    @patch('valuation.tasks.requests.post')
    def test_ml_service_connection_error_handling(self, mock_post):
        """Test handling of ML service connection errors"""
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        # Execute task
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(self.test_request.id)

        # Verify error handling  
        self.assertEqual(result['status'], 'error')
        self.assertIn('ML service communication error', result['error'])
        self.assertIn('Connection refused', result['error'])

    def test_nonexistent_request_handling(self):
        """Test handling of non-existent ValuationRequest"""
        # Execute task with non-existent ID
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(99999)

        # Verify error handling
        self.assertEqual(result['status'], 'error')
        self.assertIn('ValuationRequest 99999 not found', result['error'])

    @patch('valuation.tasks.requests.post')
    def test_nullable_district_handling(self, mock_post):
        """Test handling of nullable district field"""
        # Create request without district (empty string, not None)
        no_district_request = ValuationRequest.objects.create(
            city="Warsaw",
            district="",  # Empty string (blank=True, but not null=True)
            area_sqm=100.0,
            rooms=4,
            status=ValuationRequest.Status.PENDING
        )

        # Mock ML service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'predicted_price': 1200000.0,
            'input_data': {'city': 'Warsaw', 'district': 'Unknown', 'area_sqm': 100.0, 'rooms': 4}
        }
        mock_post.return_value = mock_response

        # Execute task
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(no_district_request.id)

        # Verify success
        self.assertEqual(result['status'], 'success')
        
        # Verify ML service called with "Unknown" district
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['district'], 'Unknown')

    @patch('valuation.tasks.requests.post')
    def test_status_progression(self, mock_post):
        """Test proper status progression through workflow"""
        # Mock ML service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'predicted_price': 750000.0,
            'input_data': {'city': 'Gdansk', 'area_sqm': 80.0, 'rooms': 2}
        }
        mock_post.return_value = mock_response

        # Verify initial status
        self.assertEqual(self.test_request.status, ValuationRequest.Status.PENDING)

        # Execute task with controlled timing
        with patch('valuation.tasks.time.sleep') as mock_sleep:
            result = process_valuation_request(self.test_request.id)

        # Verify final status
        self.test_request.refresh_from_db()
        self.assertEqual(self.test_request.status, ValuationRequest.Status.DONE)
        
        # Verify sleep was called for UX delays
        self.assertEqual(mock_sleep.call_count, 2)  # Initial delay + processing delay


class ValuationIntegrationTest(TestCase):
    """Integration tests for complete valuation workflow"""

    @patch('valuation.tasks.requests.post')
    def test_end_to_end_valuation_workflow(self, mock_post):
        """Test complete end-to-end async valuation workflow"""
        # Mock ML service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'predicted_price': 1500000.0,
            'input_data': {
                'city': 'Warsaw',
                'district': 'Mokotow', 
                'area_sqm': 120.0,
                'rooms': 4
            }
        }
        mock_post.return_value = mock_response

        # Step 1: Submit valuation request via API
        response = self.client.post(
            '/api/valuation/',
            data={
                'city': 'Warsaw',
                'district': 'Mokotow',
                'area_sqm': 120.0,
                'rooms': 4
            },
            content_type='application/json'
        )

        # Verify submission success
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['status'], 'PENDING')
        
        request_id = response_data['request_id']
        task_id = response_data['task_id']
        
        # Verify database record created
        valuation_request = ValuationRequest.objects.get(id=request_id)
        self.assertEqual(valuation_request.status, ValuationRequest.Status.PENDING)
        self.assertEqual(valuation_request.celery_task_id, task_id)

        # Step 2: Process async task (simulate Celery execution)
        with patch('valuation.tasks.time.sleep'):
            result = process_valuation_request(request_id)

        # Step 3: Verify complete success
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['estimated_price'], 1500000)
        
        # Verify database final state
        valuation_request.refresh_from_db()
        self.assertEqual(valuation_request.status, ValuationRequest.Status.DONE)
        
        results = ValuationResult.objects.filter(request=valuation_request)
        self.assertEqual(results.count(), 1)
        
        final_result = results.first()
        self.assertEqual(final_result.estimated_price, 1500000)
        self.assertEqual(final_result.price_per_sqm, 12500)  # 1500000 / 120

    def test_form_validation_integration(self):
        """Test form validation with model constraints"""
        # Test rooms validation (1-20 constraint)
        invalid_data = {
            'city': 'TestCity',
            'district': 'TestDistrict', 
            'area_sqm': 100.0,
            'rooms': 25  # Exceeds max of 20
        }

        response = self.client.post(
            '/api/valuation/',
            data=invalid_data,
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertFalse(response_data['success'])
        self.assertIn('rooms', response_data['errors'])

        # No database record should be created
        self.assertEqual(ValuationRequest.objects.count(), 0)

    def test_concurrent_requests_handling(self):
        """Test system handles multiple concurrent requests properly"""
        # Create multiple valuation requests
        test_data = [
            {'city': 'Warsaw', 'district': 'Center', 'area_sqm': 50.0, 'rooms': 2},
            {'city': 'Krakow', 'district': 'Old Town', 'area_sqm': 75.0, 'rooms': 3}, 
            {'city': 'Gdansk', 'district': 'Main City', 'area_sqm': 100.0, 'rooms': 4}
        ]

        request_ids = []
        task_ids = []

        # Submit multiple requests
        for data in test_data:
            response = self.client.post(
                '/api/valuation/',
                data=data,
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            response_data = response.json()
            request_ids.append(response_data['request_id'])
            task_ids.append(response_data['task_id'])

        # Verify all requests created with unique IDs
        self.assertEqual(len(set(request_ids)), 3)  # All unique
        self.assertEqual(len(set(task_ids)), 3)     # All unique
        self.assertEqual(ValuationRequest.objects.count(), 3)

        # Verify each request has proper initial state
        for req_id in request_ids:
            request = ValuationRequest.objects.get(id=req_id)
            self.assertEqual(request.status, ValuationRequest.Status.PENDING)
            self.assertIsNotNone(request.celery_task_id)


class ValuationModelTest(TestCase):
    """Test ValuationRequest and ValuationResult models"""

    def test_valuation_request_model_creation(self):
        """Test creating ValuationRequest with all fields"""
        request = ValuationRequest.objects.create(
            city="Poznan",
            district="Centrum", 
            area_sqm=85.5,
            rooms=3,
            status=ValuationRequest.Status.PENDING,
            celery_task_id="test-task-id"
        )
        
        self.assertEqual(request.city, "Poznan")
        self.assertEqual(request.district, "Centrum")
        self.assertEqual(request.area_sqm, 85.5)
        self.assertEqual(request.rooms, 3)
        self.assertEqual(request.status, ValuationRequest.Status.PENDING)
        self.assertEqual(request.celery_task_id, "test-task-id")
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.edited_at)

    def test_valuation_request_nullable_fields(self):
        """Test creating ValuationRequest with blank fields"""
        request = ValuationRequest.objects.create(
            city="TestCity",
            district="",  # Blank string (not NULL)
            area_sqm=100.0,
            rooms=2,
            celery_task_id=""  # Blank string
        )
        
        self.assertEqual(request.city, "TestCity")
        self.assertEqual(request.district, "")
        self.assertEqual(request.celery_task_id, "")

    def test_valuation_request_constraints(self):
        """Test model field constraints"""
        
        # Test area_sqm minimum constraint
        request = ValuationRequest(
            city="Test", 
            area_sqm=5.0,  # Below minimum of 10
            rooms=2
        )
        
        with self.assertRaises(ValidationError):
            request.full_clean()

        # Test rooms maximum constraint  
        request = ValuationRequest(
            city="Test",
            area_sqm=100.0,
            rooms=25  # Above maximum of 20
        )
        
        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_valuation_result_model_creation(self):
        """Test creating ValuationResult"""
        # First create request
        request = ValuationRequest.objects.create(
            city="Wroclaw",
            area_sqm=75.0,
            rooms=3
        )
        
        # Create result
        result = ValuationResult.objects.create(
            request=request,
            estimated_price=900000,
            price_per_sqm=12000,
            model_version="v2.0"
        )
        
        self.assertEqual(result.request, request)
        self.assertEqual(result.estimated_price, 900000)
        self.assertEqual(result.price_per_sqm, 12000)
        self.assertEqual(result.model_version, "v2.0")
        self.assertIsNotNone(result.created_at)

    def test_valuation_result_relationship(self):
        """Test relationship between ValuationRequest and ValuationResult"""
        request = ValuationRequest.objects.create(
            city="Lublin",
            area_sqm=60.0,
            rooms=2
        )
        
        # Create one result for the request
        result1 = ValuationResult.objects.create(
            request=request,
            estimated_price=500000,
            price_per_sqm=8333
        )
        
        # Verify the relationship works
        self.assertEqual(request.result, result1)
        self.assertEqual(result1.request, request)
        
        # Try to create another result for the same request (should fail due to OneToOne)
        with self.assertRaises(Exception):
            ValuationResult.objects.create(
                request=request,
                estimated_price=520000, 
                price_per_sqm=8666
            )

    def test_model_string_representations(self):   
        """Test __str__ methods of models"""
        request = ValuationRequest.objects.create(
            city="Katowice",
            area_sqm=90.0,
            rooms=4
        )
        
        # Test request string representation
        expected_str = f"ValuationRequest for {request.city}, {request.district} - {request.area_sqm} sqm, {request.rooms} rooms"
        self.assertEqual(str(request), expected_str)
        
        result = ValuationResult.objects.create(
            request=request,
            estimated_price=750000,
            price_per_sqm=8333
        )
        
        # Test result string representation  
        expected_result_str = f"ValuationResult for property {request} - Estimated Price: 750000"
        self.assertEqual(str(result), expected_result_str)


class ValuationFormTest(TestCase):
    """Test ValuationRequestForm validation and functionality"""

    def test_valid_form_data(self):
        """Test form with valid data"""
        from .forms import ValuationRequestForm
        
        form_data = {
            'city': 'Szczecin',
            'district': 'Centrum',
            'area_sqm': 95.5,
            'rooms': 3
        }
        
        form = ValuationRequestForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test saving
        request = form.save()
        self.assertEqual(request.city, 'Szczecin')
        self.assertEqual(request.district, 'Centrum') 
        self.assertEqual(request.area_sqm, 95.5)
        self.assertEqual(request.rooms, 3)

    def test_form_required_fields(self):
        """Test form with missing required fields"""
        from .forms import ValuationRequestForm
        
        form = ValuationRequestForm(data={})
        self.assertFalse(form.is_valid())
        
        required_fields = ['city', 'area_sqm', 'rooms']
        for field in required_fields:
            self.assertIn(field, form.errors)

    def test_form_optional_district(self):  
        """Test form with optional district field"""
        
        form_data = {
            'city': 'Torun',
            # district omitted (optional)
            'area_sqm': 70.0,
            'rooms': 2
        }
        
        form = ValuationRequestForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        request = form.save()
        self.assertEqual(request.district, '')  # Empty string, not None

    def test_form_widgets_and_help_text(self):
        """Test form widgets and help text are properly configured"""
        
        form = ValuationRequestForm()
        
        # Test widget types
        self.assertIsInstance(form.fields['city'].widget, forms.TextInput)
        self.assertIsInstance(form.fields['area_sqm'].widget, forms.NumberInput) 
        self.assertIsInstance(form.fields['rooms'].widget, forms.NumberInput)
        
        # Test basic widget attributes
        area_widget = form.fields['area_sqm'].widget
        rooms_widget = form.fields['rooms'].widget
        
        self.assertEqual(area_widget.attrs['min'], '10')
        self.assertEqual(area_widget.attrs['max'], '10000') 
        self.assertEqual(rooms_widget.attrs['max'], '20')
        
        # Test help text is present 
        self.assertIn('10-10,000', form.fields['area_sqm'].help_text)
        self.assertIn('1-20', form.fields['rooms'].help_text)
        
        # Test form validation works correctly
        valid_data = {
            'city': 'Warszawa',
            'area_sqm': 100.0,
            'rooms': 3
        }
        form_with_data = ValuationRequestForm(data=valid_data)
        self.assertTrue(form_with_data.is_valid())
