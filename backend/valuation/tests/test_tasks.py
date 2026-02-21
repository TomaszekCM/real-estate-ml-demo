"""  
Celery task tests - testing async task functionality and endpoints
"""
from django.test import TestCase
from celery.result import AsyncResult
from unittest.mock import patch, Mock
import requests
import time
from ..models import ValuationRequest, ValuationResult
from ..tasks import process_valuation_request


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
            from ..tasks import hello_world
            task_import_success = True
        except ImportError:
            task_import_success = False
        
        self.assertTrue(task_import_success, "Failed to import Celery task")

    def test_hello_world_task_sync(self):
        """Test hello_world task execution (synchronous mode for testing)"""  
        from ..tasks import hello_world
        
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
        from ..tasks import debug_sleep
        
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