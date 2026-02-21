"""
Model and form tests - testing data models and form validation
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django import forms
from ..models import ValuationRequest, ValuationResult
from ..forms import ValuationRequestForm


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