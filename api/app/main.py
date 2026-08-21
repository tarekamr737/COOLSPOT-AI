"""Application entry point for the COOLSPOT AI API."""

from fastapi import FastAPI

from api.app.routers.decision import router as decision_router
from api.app.schemas import HealthResponse

app = FastAPI(title="COOLSPOT AI API", version="0.1.0")
app.include_router(decision_router)


@app.get("/health")
def health() -> HealthResponse:
    """Report that the API process is ready to serve requests."""

    return HealthResponse()
