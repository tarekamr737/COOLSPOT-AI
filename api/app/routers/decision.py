"""Offline decision-support routes."""

from fastapi import APIRouter, Header, HTTPException

from api.app.schemas import (
    CandidateListResponse,
    DataStatusResponse,
    ExplanationRequest,
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
from api.app.services.explanations import GroundedExplanation, explain_with_optional_llm
from api.app.services.live_refresh import (
    RefreshPreflightError,
    RefreshRequest,
    RefreshStatus,
    refresh_coordinator,
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


@router.post("/sites/{site_id}/explanation")
async def explain_site(site_id: str, request: ExplanationRequest) -> GroundedExplanation:
    response = site_response(site_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"site '{site_id}' was not found")
    option = next(
        (item for item in response.options if item.candidate.id == request.candidate_id),
        None,
    )
    if option is None:
        raise HTTPException(
            status_code=404,
            detail=f"candidate '{request.candidate_id}' was not found at site '{site_id}'",
        )
    try:
        portfolio = optimize_portfolio(request.budget_usd)
        return await explain_with_optional_llm(
            candidate=option.candidate,
            tile=option.tile,
            intervention=option.intervention,
            portfolio=portfolio,
            regenerate=request.regenerate,
        )
    except ValueError as error:
        status_code = 409 if "is not selected" in str(error) else 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except OptimizationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/methodology")
def get_methodology() -> MethodologyResponse:
    return methodology_response()


@router.get("/data-status")
def get_data_status() -> DataStatusResponse:
    return data_status_response()


@router.get("/refresh/status")
def get_refresh_status() -> RefreshStatus:
    return refresh_coordinator.status()


@router.post("/refresh")
async def refresh_data(
    request: RefreshRequest,
    x_refresh_token: str = Header(default=""),
) -> RefreshStatus:
    try:
        return await refresh_coordinator.start(
            token=x_refresh_token,
            analysis_date=request.analysis_date,
        )
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except RefreshPreflightError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
