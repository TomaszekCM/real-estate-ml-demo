"""
View and API tests - testing web views and AJAX endpoints
"""
from django.test import TestCase
import json
from unittest.mock import patch, Mock
from datetime import datetime
from ..models import ValuationRequest, ValuationResult


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


class ValuationStatusPollingTest(TestCase):
    """Test the status polling endpoint for valuation requests"""
    
    def setUp(self):
        """Set up test data"""
        self.status_url_template = '/api/valuation/{}/status/'
        
    def test_status_endpoint_for_pending_request(self):
        """Test status endpoint returns correct data for PENDING request"""
        # Create a PENDING request
        request = ValuationRequest.objects.create(
            city="Warszawa",
            district="Centrum",
            area_sqm=75.0,
            rooms=2,
            status=ValuationRequest.Status.PENDING,
            celery_task_id="test-task-id-123"
        )
        
        # Test status endpoint
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['request_id'], request.id)
        self.assertEqual(data['status'], 'PENDING')
        self.assertEqual(data['task_id'], 'test-task-id-123')
        self.assertIn('created_at', data)
        self.assertNotIn('result', data)  # No result for pending request
        
    def test_status_endpoint_for_processing_request(self):
        """Test status endpoint returns correct data for PROCESSING request"""
        request = ValuationRequest.objects.create(
            city="Kraków", 
            area_sqm=90.0,
            rooms=3,
            status=ValuationRequest.Status.PROCESSING,
            celery_task_id="processing-task-456"
        )
        
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['request_id'], request.id)
        self.assertEqual(data['status'], 'PROCESSING')
        self.assertEqual(data['task_id'], 'processing-task-456')
        self.assertNotIn('result', data)  # No result while processing
        
    def test_status_endpoint_for_completed_request_with_result(self):
        """Test status endpoint returns result data for DONE request"""
        # Create completed request
        request = ValuationRequest.objects.create(
            city="Gdańsk",
            district="Główne Miasto", 
            area_sqm=110.0,
            rooms=4,
            status=ValuationRequest.Status.DONE,
            celery_task_id="completed-task-789"
        )
        
        # Create associated result
        result = ValuationResult.objects.create(
            request=request,
            estimated_price=1500000,
            price_per_sqm=13636,
            model_version="v1.0"
        )
        
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['request_id'], request.id)
        self.assertEqual(data['status'], 'DONE')
        self.assertIn('result', data)
        
        # Validate result data
        result_data = data['result']
        self.assertEqual(result_data['estimated_price'], 1500000)
        self.assertEqual(result_data['price_per_sqm'], 13636)
        self.assertEqual(result_data['model_version'], "v1.0")
        self.assertIn('created_at', result_data)
        
    def test_status_endpoint_for_failed_request(self):
        """Test status endpoint returns correct data for FAILED request"""
        request = ValuationRequest.objects.create(
            city="Wrocław",
            area_sqm=85.0,
            rooms=3,
            status=ValuationRequest.Status.FAILED,
            celery_task_id="failed-task-999"
        )
        
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['request_id'], request.id)
        self.assertEqual(data['status'], 'FAILED')
        self.assertEqual(data['task_id'], 'failed-task-999')
        self.assertNotIn('result', data)  # No result for failed request
        
    def test_status_endpoint_for_done_request_without_result(self):
        """Test status endpoint handles DONE request missing result gracefully"""
        # Create DONE request without result (data inconsistency)
        request = ValuationRequest.objects.create(
            city="Poznań",
            area_sqm=95.0, 
            rooms=3,
            status=ValuationRequest.Status.DONE,
            celery_task_id="orphaned-task-555"
        )
        # Note: No ValuationResult created
        
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should change status to FAILED when result is missing
        self.assertEqual(data['request_id'], request.id)
        self.assertEqual(data['status'], 'FAILED')
        self.assertEqual(data['error'], 'Result not found')
        
    def test_status_endpoint_for_nonexistent_request(self):
        """Test status endpoint returns 404 for nonexistent request"""
        nonexistent_id = 99999
        response = self.client.get(self.status_url_template.format(nonexistent_id))
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        
        self.assertEqual(data['error'], 'Valuation request not found')
        
    def test_status_endpoint_methods(self):
        """Test that status endpoint only accepts GET requests"""
        request = ValuationRequest.objects.create(
            city="Łódź",
            area_sqm=70.0,
            rooms=2,
            status=ValuationRequest.Status.PENDING
        )
        
        url = self.status_url_template.format(request.id)
        
        # GET should work
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # POST should not be allowed
        response = self.client.post(url, {'test': 'data'})
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
        
        # PUT should not be allowed
        response = self.client.put(url, {'test': 'data'})
        self.assertEqual(response.status_code, 405)
        
    def test_status_endpoint_json_format(self):
        """Test that status endpoint returns valid JSON with expected fields"""
        request = ValuationRequest.objects.create(
            city="Katowice",
            district="Śródmieście",
            area_sqm=80.0,
            rooms=2,
            status=ValuationRequest.Status.PENDING,
            celery_task_id="json-test-task"
        )
        
        response = self.client.get(self.status_url_template.format(request.id))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        
        # Check required fields
        expected_fields = ['request_id', 'status', 'created_at', 'task_id']
        for field in expected_fields:
            self.assertIn(field, data, f"Missing required field: {field}")
        
        # Check data types
        self.assertIsInstance(data['request_id'], int)
        self.assertIsInstance(data['status'], str)
        self.assertIsInstance(data['created_at'], str) # ISO format
        
        # Validate ISO datetime format
        try:
            datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        except ValueError:
            self.fail("created_at is not in valid ISO format")