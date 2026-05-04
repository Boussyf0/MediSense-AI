from __future__ import annotations

import uuid
from typing import Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_any_staff, require_secretary
from app.db.models.appointment import Appointment
from app.db.models.ml_feedback import MLFeedback
from app.db.session import get_db
from app.services.noshow_predictor import (
    FeatureValidationError,
    ModelNotReadyError,
    noshow_predictor,
)

router = APIRouter(prefix="/predict", tags=["ml"])


class FeedbackRequest(BaseModel):
    appointment_uuid: uuid.UUID
    actual_status: Literal["COMPLETED", "NO_SHOW"]
    was_predicted_correctly: bool
    prediction_prob: float = Field(..., ge=0, le=1)
    model_version: str = Field(..., min_length=1, max_length=20)
    doctor_feedback: str | None = Field(default=None, max_length=500)


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_ml_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(require_secretary),
):
    """
    POST /api/v1/predict/feedback
    Closes the MLOps loop by saving the ground truth for an appointment.
    """
    appointment_stmt = select(Appointment).where(Appointment.appointment_uuid == request.appointment_uuid)
    appointment_result = await db.execute(appointment_stmt)
    appointment = appointment_result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    existing_feedback_stmt = select(MLFeedback).where(MLFeedback.appointment_uuid == request.appointment_uuid)
    existing_feedback_result = await db.execute(existing_feedback_stmt)
    existing_feedback = existing_feedback_result.scalar_one_or_none()
    if existing_feedback is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already exists for this appointment",
        )

    feedback = MLFeedback(
        appointment_uuid=request.appointment_uuid,
        actual_status=request.actual_status,
        was_predicted_correctly=request.was_predicted_correctly,
        prediction_prob=request.prediction_prob,
        model_version=request.model_version,
        doctor_feedback=request.doctor_feedback
    )
    db.add(feedback)
    await db.flush()
    return {"status": "success", "detail": "Feedback saved for retraining loop"}


class NoShowRequest(BaseModel):
    age: int = Field(..., ge=0, le=120)
    sex: str = Field(..., pattern="^[MF]$")
    distance_to_clinic: float = Field(..., ge=0)
    weather_score: float = Field(..., ge=0, le=1)
    previous_noshows: int = Field(..., ge=0)
    days_since_booking: int = Field(..., ge=0)
    day_of_week: int = Field(..., ge=0, le=6)
    appointment_hour: int = Field(..., ge=0, le=23)
    chronic_conditions_count: int = Field(..., ge=0)

class NoShowResponse(BaseModel):
    noshow_probability: float
    risk_color: str
    shap_contributions: Dict[str, float]
    model_version: str


@router.post("/noshow", response_model=NoShowResponse)
async def predict_noshow(
    request: NoShowRequest,
    _current_user: TokenPayload = Depends(require_any_staff),
):
    """
    POST /api/v1/predict/noshow
    Returns no-show probability and SHAP contributions for a given patient context.
    Strictly follows Sprint 5 requirements for explainability.
    """
    features = request.model_dump()
    try:
        return noshow_predictor.predict(features)
    except FeatureValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ModelNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
