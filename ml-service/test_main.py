import pytest
from fastapi.testclient import TestClient
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from app.main import app, model


client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_endpoint_returns_ok(self):
        """Test that health endpoint returns OK status"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "model_loaded" in data
        assert "version" in data
        assert "model_path_exists" in data
    
    def test_health_endpoint_structure(self):
        """Test that health endpoint has correct structure"""
        response = client.get("/health")
        data = response.json()
        
        expected_keys = {"status", "model_loaded", "version", "model_path_exists"}
        assert set(data.keys()) == expected_keys


class TestPredictEndpoint:
    """Test prediction endpoint"""
    
    def test_predict_valid_input(self):
        """Test prediction with valid input data"""
        # Skip if model not loaded
        if model is None:
            pytest.skip("Model not loaded - cannot test prediction")
            
        valid_data = {
            "city": "Warsaw",
            "district": "Center",
            "area_sqm": 75.0,
            "rooms": 3
        }
        
        response = client.post("/predict", json=valid_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "predicted_price" in data
        assert "input_data" in data
        assert isinstance(data["predicted_price"], float)
        assert data["input_data"] == valid_data
    
    def test_predict_invalid_area(self):
        """Test prediction with invalid area (negative)"""
        invalid_data = {
            "city": "Warsaw", 
            "district": "Center",
            "area_sqm": -10.0,  # Invalid: negative area
            "rooms": 3
        }
        
        response = client.post("/predict", json=invalid_data)
        assert response.status_code == 422  # Validation error
        
        data = response.json()
        assert "detail" in data
        # Check that error mentions area_sqm
        error_fields = [error["loc"][-1] for error in data["detail"]]
        assert "area_sqm" in error_fields
    
    def test_predict_invalid_rooms(self):
        """Test prediction with invalid rooms (zero)"""
        invalid_data = {
            "city": "Warsaw",
            "district": "Center", 
            "area_sqm": 75.0,
            "rooms": 0  # Invalid: zero rooms
        }
        
        response = client.post("/predict", json=invalid_data)
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
        error_fields = [error["loc"][-1] for error in data["detail"]]
        assert "rooms" in error_fields
    
    def test_predict_too_many_rooms(self):
        """Test prediction with too many rooms"""
        invalid_data = {
            "city": "Warsaw",
            "district": "Center",
            "area_sqm": 75.0,
            "rooms": 15  # Invalid: more than 10 rooms
        }
        
        response = client.post("/predict", json=invalid_data)
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
    
    def test_predict_missing_fields(self):
        """Test prediction with missing required fields"""
        incomplete_data = {
            "city": "Warsaw",
            # Missing district, area_sqm, rooms
        }
        
        response = client.post("/predict", json=incomplete_data)
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
        # Should have errors for missing fields
        assert len(data["detail"]) >= 3  # district, area_sqm, rooms missing
    
    @patch('app.main.model', None)
    def test_predict_model_not_loaded(self):
        """Test prediction when model is not loaded"""
        valid_data = {
            "city": "Warsaw",
            "district": "Center",
            "area_sqm": 75.0,
            "rooms": 3
        }
        
        response = client.post("/predict", json=valid_data)
        assert response.status_code == 503  # Service unavailable
        
        data = response.json()
        assert "detail" in data
        assert "Model not available" in data["detail"]
    
    def test_predict_different_cities(self):
        """Test prediction with different cities"""
        if model is None:
            pytest.skip("Model not loaded - cannot test prediction")
            
        cities = ["Warsaw", "Krakow", "Gdansk"]
        
        for city in cities:
            data = {
                "city": city,
                "district": "Center",
                "area_sqm": 75.0,
                "rooms": 3
            }
            
            response = client.post("/predict", json=data)
            assert response.status_code == 200
            
            result = response.json()
            assert result["input_data"]["city"] == city
            assert isinstance(result["predicted_price"], float)


class TestAPIDocumentation:
    """Test API documentation endpoints"""
    
    def test_openapi_json(self):
        """Test that OpenAPI schema is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "Real Estate ML Service"
    
    def test_docs_contain_auth_warning(self):
        """Test that API docs mention authentication warning"""
        response = client.get("/openapi.json")
        schema = response.json()
        
        description = schema["info"]["description"]
        assert "Authentication not implemented" in description or "⚠️" in description


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])