"""Promote the completed Pacoima time-of-measure activity into a committed artifact."""

from __future__ import annotations

import hashlib

from api.app.fortyguard_models import (
    ActivityLifecycle,
    FortyGuardEndpoint,
    HeatmapRequest,
    HeatmapResult,
)
from api.app.services.fortyguard import CachedActivity, canonical_request_hash
from api.app.services.heatmap_data import (
    CachedHeatmapLayer,
    PacoimaTimeOfMeasureArtifact,
)
from scripts.measure_fortyguard_heatmap import (
    AOI_PATH,
    CACHE_ROOT,
    ROOT,
    MeasurementReport,
    write_model,
)
from scripts.measure_fortyguard_time_of_measure import (
    REPORT_PATH,
    build_time_of_measure_request,
)

OUTPUT_PATH = ROOT / "data" / "processed" / "pacoima_fortyguard_time_of_measure.json"


def build_artifact() -> PacoimaTimeOfMeasureArtifact:
    """Validate and freeze the existing cached result without a vendor call."""

    request = build_time_of_measure_request()
    if request.granularity != 100:
        raise RuntimeError("frozen time-of-measure request must use 100 m granularity")
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)
    report = MeasurementReport.model_validate_json(REPORT_PATH.read_text(encoding="utf-8"))
    if report.status != "Completed" or report.request_hash != request_hash:
        raise RuntimeError("completed time-of-measure report does not match the frozen request")

    cache_path = CACHE_ROOT / "requests" / f"{request_hash}.json"
    cached = CachedActivity.model_validate_json(cache_path.read_text(encoding="utf-8"))
    if (
        cached.status != ActivityLifecycle.COMPLETED
        or cached.endpoint != FortyGuardEndpoint.HEATMAP
        or cached.request_hash != request_hash
        or cached.activity_id != report.activity_id
        or cached.result is None
    ):
        raise RuntimeError(
            "cached time-of-measure activity is incomplete or has mismatched provenance"
        )
    if HeatmapRequest.model_validate(cached.request_payload) != request:
        raise RuntimeError("cached time-of-measure payload does not match the frozen request")

    result = HeatmapResult.model_validate(cached.result)
    return PacoimaTimeOfMeasureArtifact(
        license_notes=(
            "FortyGuard hackathon API output cached for the COOLSPOT AI demonstration; "
            "not a ground-observation dataset."
        ),
        aoi_sha256=hashlib.sha256(AOI_PATH.read_bytes()).hexdigest().upper(),
        generated_at=report.measured_at,
        layer=CachedHeatmapLayer(
            analytic_type="time_of_measure",
            activity_id=report.activity_id,
            request_hash=request_hash,
            completed_at=report.measured_at,
            granularity_m=request.granularity,
            date_time=request.date_time,
            threshold_c=request.threshold,
            direction=request.direction,
            observed_credit_delta=report.observed_credit_delta,
            threshold_rationale=(
                "Threshold and direction are ignored by the time-of-measure analytic."
            ),
            feature_count=len(result.map_data.features),
            result=result,
        ),
    )


def main() -> None:
    artifact = build_artifact()
    write_model(OUTPUT_PATH, artifact)
    print(
        f"Cached time_of_measure={artifact.layer.feature_count} tiles/"
        f"{artifact.layer.observed_credit_delta} credits"
    )


if __name__ == "__main__":
    main()
