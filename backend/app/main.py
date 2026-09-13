from importlib import import_module


try:
    FastAPI = import_module("fastapi").FastAPI
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "FastAPI is not installed. Install it with: pip install fastapi"
    ) from exc

app = FastAPI(
    title="AuthentiScore API",
    description="AI-Powered Fake Social Media Profile Detection System",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "project": "AuthentiScore",
        "message": "API is running",
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }