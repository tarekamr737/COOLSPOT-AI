"""Offline decision-support routes."""

from fastapi import APIRouter, HTTPException

from api.app.schemas import (
    CandidateListResponse,
    DataStatusResponse,
    LayerName,
    LayerResponse,
    MethodologyResponse,
    OptimizeRequest,
    PilotResponse,
    SiteResponse,
)
from api.app.services.decision_api import (
    candidates_response,
    data_status_response,
    layer_response,
    methodology_response,
    pilot_response,
    site_response,
)
from api.app.services.optimizer import OptimizationError, PortfolioResult, optimize_portfolio

router = APIRouter(prefix="/v1")


@router.get("/pilot")
def get_pilot() -> PilotResponse:
    return pilot_response()


@router.get("/layers/{layer}")
def get_layer(layer: LayerName) -> LayerResponse:
    return layer_response(layer)


@router.get("/candidates")
def get_candidates() -> CandidateListResponse:
    return candidates_response()


@router.post("/optimize")
def optimize(request: OptimizeRequest) -> PortfolioResult:
    try:
        return optimize_portfolio(request.budget_usd)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OptimizationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/sites/{site_id}")
def get_site(site_id: str) -> SiteResponse:
    response = site_response(site_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"site '{site_id}' was not found")
    return response


@router.get("/methodology")
def get_methodology() -> MethodologyResponse:
    return methodology_response()


@router.get("/data-status")
def get_data_status() -> DataStatusResponse:
    return data_status_response()
