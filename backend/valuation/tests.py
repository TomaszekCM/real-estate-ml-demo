from django.test import TestCase
from django.core.cache import cache
from django.db import connection
import redis
from django.conf import settings
from .models import ValuationRequest, ValuationResult
from celery.result import AsyncResult


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
