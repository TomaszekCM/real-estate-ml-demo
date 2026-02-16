from fastapi import FastAPI
import joblib
import pandas as pd
import os

app = FastAPI(
    title="Real Estate ML Service",
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

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "version": "1.0.0",
        "model_path_exists": os.path.exists(model_path)
    }



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