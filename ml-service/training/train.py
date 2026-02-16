import os
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

MODEL_PATH = "models/regression_model.joblib"


def generate_synthetic_data(n_samples=1000):
    cities = ["Warsaw", "Krakow", "Gdansk"]
    districts = ["Center", "North", "South"]

    data = []

    for _ in range(n_samples):
        city = np.random.choice(cities)
        district = np.random.choice(districts)
        area = np.random.uniform(30, 120)
        rooms = np.random.randint(1, 6)

        base_price = area * 12000 + rooms * 50000

        if city == "Warsaw":
            base_price *= 1.3
        if district == "Center":
            base_price *= 1.2

        noise = np.random.normal(0, 50000)

        price = base_price + noise

        data.append([city, district, area, rooms, price])

    df = pd.DataFrame(
        data,
        columns=["city", "district", "area_sqm", "rooms", "price"]
    )

    return df


def train():
    df = generate_synthetic_data()

    X = df[["city", "district", "area_sqm", "rooms"]]
    y = df["price"]

    categorical_features = ["city", "district"]
    numeric_features = ["area_sqm", "rooms"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", "passthrough", numeric_features),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", LinearRegression()),
        ]
    )

    pipeline.fit(X, y)

    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    print("Model trained and saved!")


if __name__ == "__main__":
    train()
