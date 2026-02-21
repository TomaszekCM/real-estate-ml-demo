"""
Integration tests - testing complete end-to-end workflows
"""
from django.test import TestCase
import json
from unittest.mock import patch, Mock
from ..models import ValuationRequest, ValuationResult
from ..tasks import process_valuation_request


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


class ValuationPollingIntegrationTest(TestCase):
    """Integration tests for the complete polling workflow"""
    
    @patch('valuation.tasks.process_valuation_request.delay')
    def test_complete_polling_workflow_simulation(self, mock_task):
        """Test complete workflow from form submission to polling result"""
        # Mock Celery task
        mock_result = Mock()
        mock_result.id = "integration-test-task-id"
        mock_task.return_value = mock_result
        
        # Step 1: Submit valuation form
        form_data = {
            'city': 'Warszawa',
            'district': 'Mokotów',
            'area_sqm': 95.0,
            'rooms': 3
        }
        
        response = self.client.post(
            '/api/valuation/',
            data=json.dumps(form_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        form_response = response.json()
        self.assertTrue(form_response['success'])
        
        request_id = form_response['request_id']
        self.assertEqual(form_response['status'], 'PENDING')
        
        # Step 2: Verify initial polling state
        status_response = self.client.get(f'/api/valuation/{request_id}/status/')
        self.assertEqual(status_response.status_code, 200)
        
        status_data = status_response.json()
        self.assertEqual(status_data['status'], 'PENDING')
        self.assertEqual(status_data['request_id'], request_id)
        
        # Step 3: Simulate processing state
        request = ValuationRequest.objects.get(id=request_id)
        request.status = ValuationRequest.Status.PROCESSING
        request.save()
        
        status_response = self.client.get(f'/api/valuation/{request_id}/status/')
        status_data = status_response.json()
        self.assertEqual(status_data['status'], 'PROCESSING')
        
        # Step 4: Simulate completion with result
        request.status = ValuationRequest.Status.DONE
        request.save()
        
        ValuationResult.objects.create(
            request=request,
            estimated_price=1850000,
            price_per_sqm=19473,
            model_version="v1.0"
        )
        
        # Final polling should return complete result
        status_response = self.client.get(f'/api/valuation/{request_id}/status/')
        final_data = status_response.json()
        
        self.assertEqual(final_data['status'], 'DONE')
        self.assertIn('result', final_data)
        self.assertEqual(final_data['result']['estimated_price'], 1850000)
        self.assertEqual(final_data['result']['price_per_sqm'], 19473)
        
    def test_concurrent_status_polling(self):
        """Test that multiple concurrent status polls don't interfere"""
        # Create multiple requests
        requests = []
        for i in range(3):
            request = ValuationRequest.objects.create(
                city=f"City{i}",
                area_sqm=80.0 + i * 10,
                rooms=2 + i,
                status=ValuationRequest.Status.PENDING,
                celery_task_id=f"concurrent-task-{i}"
            )
            requests.append(request)
        
        # Poll all statuses concurrently (simulated) 
        responses = []
        for request in requests:
            response = self.client.get(f'/api/valuation/{request.id}/status/')
            responses.append(response)
        
        # All should succeed
        for i, response in enumerate(responses):
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['request_id'], requests[i].id)
            self.assertEqual(data['status'], 'PENDING')
            self.assertEqual(data['task_id'], f'concurrent-task-{i}')