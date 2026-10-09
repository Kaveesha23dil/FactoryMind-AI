
from fastapi import FastAPI

app = FastAPI(title="FactoryMind AI API")

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "project": "FactoryMind AI",
        "version": "0.1.0"
    }
