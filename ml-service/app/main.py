from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import joblib
import pandas as pd
import os

# TODO: Authentication will be added in a future iteration
# Currently, all endpoints are publicly accessible without authentication

app = FastAPI(
    title="Real Estate ML Service",
    description="Machine Learning service for real estate price prediction. "
               "⚠️ Note: Authentication not implemented yet - will be added in future versions.",
    version="1.0.0"
)

# Try to load model on startup
model = None
model_path = "models/regression_model.joblib"

try:
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        print(f"Model loaded successfully from {model_path}")
    else:
        print(f"Model file not found at {model_path}")
except Exception as e:
    print(f"Error loading model: {e}")

# Pydantic models for input validation
class PropertyData(BaseModel):
    city: str = Field(..., description="City name")
    district: str = Field(..., description="District name") 
    area_sqm: float = Field(..., gt=0, description="Area in square meters")
    rooms: int = Field(..., gt=0, le=10, description="Number of rooms")

class PredictionResponse(BaseModel):
    predicted_price: float
    input_data: PropertyData

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "version": "1.0.0",
        "model_path_exists": os.path.exists(model_path)
    }

@app.post("/predict", response_model=PredictionResponse)
def predict_price(property_data: PropertyData):
    """
    Predict real estate price based on property characteristics.
    
    Note: This endpoint currently has no authentication/authorization.
    Authentication will be implemented in a future version.
    """
    # Check if model is loaded
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not available. Please check if the model file exists."
        )
    
    try:
        # Convert input to DataFrame format expected by model
        input_df = pd.DataFrame([{
            "city": property_data.city,
            "district": property_data.district,
            "area_sqm": property_data.area_sqm,
            "rooms": property_data.rooms
        }])
        
        # Make prediction
        prediction = model.predict(input_df)
        predicted_price = float(prediction[0])
        
        return PredictionResponse(
            predicted_price=predicted_price,
            input_data=property_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction error: {str(e)}"
        )



# Test model loading and prediction
if __name__ == "__main__":
    model = joblib.load("models/regression_model.joblib")
    
    # Create DataFrame with proper structure
    test_data = pd.DataFrame([{
        "city": "Warsaw",
        "district": "Center", 
        "area_sqm": 70,
        "rooms": 3
    }])
    
    prediction = model.predict(test_data)
    print(f"Predicted price: {prediction[0]:.2f} PLN")