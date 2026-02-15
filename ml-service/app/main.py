from fastapi import FastAPI

app = FastAPI(
    title="Real Estate ML Service",
    version="1.0.0"
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": False,
        "version": "1.0.0"
    }
