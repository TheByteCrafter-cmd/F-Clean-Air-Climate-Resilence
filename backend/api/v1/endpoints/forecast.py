"""
VayuDrishti — Forecast API Endpoint (Phase 1E-J2E.2)

Exposes post-inference PM2.5 air quality forecasting over +1h, +3h, and +6h target horizons
with Split Conformal prediction intervals for the Anand Vihar 8118 pilot station.
"""

import logging
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.forecast import (
    ConformalIntervalDetail,
    ForecastRequest,
    ForecastResponse,
    HorizonForecastResult,
)
from ml.src.forecasting.inference import ForecastInferenceEngine, InferenceError
from ml.src.forecasting.model_loader import ModelLoaderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecast", tags=["forecasting"])

# Module-level application-lifetime ForecastInferenceEngine instance
_inference_engine: Optional[ForecastInferenceEngine] = None
_engine_init_error: Optional[str] = None


def get_inference_engine(force_reload: bool = False) -> ForecastInferenceEngine:
    """Returns application-lifetime inference engine or raises ModelLoaderError if uninitialized."""
    global _inference_engine, _engine_init_error
    if _inference_engine is None or force_reload:
        try:
            _inference_engine = ForecastInferenceEngine()
            _engine_init_error = None
            logger.info("ForecastInferenceEngine initialized successfully for API transport layer.")
        except ModelLoaderError as mle:
            _inference_engine = None
            _engine_init_error = str(mle)
            logger.error(f"ForecastInferenceEngine failed to initialize: {mle}")
            raise mle
        except Exception as e:
            _inference_engine = None
            _engine_init_error = str(e)
            logger.error(f"Unexpected error during ForecastInferenceEngine initialization: {e}")
            raise ModelLoaderError(_engine_init_error)

    return _inference_engine


@router.post(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate PM2.5 air quality forecast predictions",
    description="""
    Accepts a leakage-safe prepared feature vector for the Anand Vihar 8118 pilot station
    and generates deterministic +1h, +3h, and +6h PM2.5 point predictions accompanied by
    unclipped 80% and 90% Split Conformal prediction intervals.
    """,
)
def generate_forecast(payload: ForecastRequest):
    """
    Executes forecast prediction endpoint request.

    Delegates prediction computation strictly to ForecastInferenceEngine.
    """
    try:
        engine = get_inference_engine()

        # Delegate inference execution
        raw_result = engine.predict(
            station_id=payload.station_id,
            prediction_timestamp=payload.prediction_timestamp,
            feature_row=payload.features,
        )

        # Map raw engine dict into ForecastResponse Pydantic schema
        horizon_list: List[HorizonForecastResult] = []
        for h_name, h_data in raw_result["horizons"].items():
            intervals_dict: Dict[str, ConformalIntervalDetail] = {}
            for level_key, iv_data in h_data["prediction_intervals"].items():
                intervals_dict[level_key] = ConformalIntervalDetail(
                    confidence_level=iv_data["confidence_level"],
                    conformal_radius=iv_data["conformal_radius"],
                    lower_bound=iv_data["lower_bound"],
                    upper_bound=iv_data["upper_bound"],
                    interval_width=iv_data["interval_width"],
                )

            horizon_list.append(
                HorizonForecastResult(
                    horizon=h_data["horizon"],
                    target_column=h_data["target_column"],
                    predicted_pm25=h_data["predicted_pm25"],
                    prediction_negative=h_data["prediction_negative"],
                    prediction_intervals=intervals_dict,
                )
            )

        return ForecastResponse(
            status="SUCCESS",
            model_scope="station_level_pilot",
            canonical_station_id=raw_result["canonical_station_id"],
            requested_station_id=raw_result["requested_station_id"],
            prediction_timestamp=raw_result["prediction_timestamp"],
            feature_count=raw_result["feature_count"],
            forecasts=horizon_list,
        )

    except ModelLoaderError as mle:
        logger.error(f"Forecast model artifact error: {mle}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="MODEL_NOT_AVAILABLE",
                    message="Forecasting model or conformal uncertainty artifacts are unavailable or invalid.",
                    details={"error": str(mle)},
                )
            ).model_dump(),
        )

    except InferenceError as ie:
        logger.warning(f"Inference validation error [{ie.error_code}]: {ie.message}")
        # Map error codes to HTTP status codes according to Correction 3
        if ie.error_code in ("MODEL_NOT_AVAILABLE", "MODEL_ARTIFACT_INVALID", "UNCERTAINTY_ARTIFACT_INVALID"):
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_400_BAD_REQUEST

        return JSONResponse(
            status_code=http_status,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=ie.error_code,
                    message=ie.message,
                    details=ie.details,
                )
            ).model_dump(),
        )

    except Exception as e:
        logger.error(f"Unexpected error during forecast API execution: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INFERENCE_ERROR",
                    message="Forecast inference failed due to an unexpected server error.",
                )
            ).model_dump(),
        )
