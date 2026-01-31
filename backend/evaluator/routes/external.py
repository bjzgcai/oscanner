"""
External API routes for third-party integrations (e.g., PQ score queries)
"""
import httpx
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel


router = APIRouter(prefix="/api/external")

# External PQ API configuration
EXTERNAL_PQ_API_URL = "https://pq.bjzgca.edu.cn:13280/api/external/query-score"
REQUEST_TIMEOUT = 30.0  # seconds


# Pydantic models for response structure
class Activity(BaseModel):
    activity_name: str
    total_score: float
    accuracy_rate: float
    total_questions: int
    answered_questions: int
    correct_answers: int
    ranking_position: Optional[int] = None
    total_participants: int
    ranking_percentile: float
    activity_started_at: str
    activity_ended_at: Optional[str] = None


class UserScoreData(BaseModel):
    external_user_id: str
    series_name: str
    total_activities: int
    participated_activities: int
    activities: list[Activity]
    query_time: str


class QueryScoreResponse(BaseModel):
    success: bool
    data: Optional[UserScoreData] = None
    error: Optional[str] = None


# In production, this should be loaded from environment or database
VALID_API_KEYS = {
    "BbjiZsAwDnLNwqXCFRLztOtZfP-0OrfU7nUsykW4s2Y",  # Default key from frontend
}


def validate_api_key(api_key: str) -> bool:
    """Validate API key for external requests"""
    return api_key in VALID_API_KEYS


@router.get("/query-score", response_model=QueryScoreResponse)
async def query_score(
    external_user_id: str = Query(..., description="External user ID"),
    series_name: str = Query(..., description="Series name (e.g., vibe-coding-2026-3)"),
    x_api_key: str = Header(..., alias="X-API-Key", description="API key for authentication"),
):
    """
    Query score data for a user from external PQ (Programming Quiz) system.

    This endpoint acts as a proxy to the external PQ API at:
    https://pq.bjzgca.edu.cn:13280/api/external/query-score
    """
    # Validate API key
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        # Make request to external PQ API
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, verify=False) as client:
            response = await client.get(
                EXTERNAL_PQ_API_URL,
                params={
                    "external_user_id": external_user_id,
                    "series_name": series_name,
                },
                headers={
                    "X-API-Key": x_api_key,
                },
            )

            # Check if request was successful
            if response.status_code != 200:
                return QueryScoreResponse(
                    success=False,
                    error=f"External API error: {response.status_code} - {response.text}",
                )

            # Parse and return the response
            data = response.json()

            # If external API already returns in our expected format, return it directly
            if isinstance(data, dict) and "success" in data:
                return QueryScoreResponse(**data)

            # Otherwise, assume it's the data payload and wrap it
            return QueryScoreResponse(success=True, data=UserScoreData(**data))

    except httpx.TimeoutException:
        return QueryScoreResponse(
            success=False,
            error="Request to external PQ API timed out",
        )
    except httpx.RequestError as e:
        return QueryScoreResponse(
            success=False,
            error=f"Failed to connect to external PQ API: {str(e)}",
        )
    except Exception as e:
        return QueryScoreResponse(
            success=False,
            error=f"Unexpected error: {str(e)}",
        )


def _get_mock_pq_data(user_id: str, series: str) -> Optional[UserScoreData]:
    """
    Generate mock PQ data for testing.
    Replace this with actual external API integration.
    """
    # Mock data for demonstration
    current_time = datetime.now().isoformat()

    mock_activities = [
        Activity(
            activity_name="Python Basics Challenge",
            total_score=85.5,
            accuracy_rate=0.85,
            total_questions=20,
            answered_questions=20,
            correct_answers=17,
            ranking_position=15,
            total_participants=150,
            ranking_percentile=0.90,
            activity_started_at="2026-01-01T09:00:00",
            activity_ended_at="2026-01-01T10:30:00",
        ),
        Activity(
            activity_name="Data Structures & Algorithms",
            total_score=72.0,
            accuracy_rate=0.72,
            total_questions=25,
            answered_questions=25,
            correct_answers=18,
            ranking_position=42,
            total_participants=180,
            ranking_percentile=0.77,
            activity_started_at="2026-01-08T09:00:00",
            activity_ended_at="2026-01-08T11:00:00",
        ),
        Activity(
            activity_name="Web Development Fundamentals",
            total_score=91.2,
            accuracy_rate=0.912,
            total_questions=30,
            answered_questions=30,
            correct_answers=27,
            ranking_position=8,
            total_participants=200,
            ranking_percentile=0.96,
            activity_started_at="2026-01-15T09:00:00",
            activity_ended_at="2026-01-15T11:30:00",
        ),
    ]

    return UserScoreData(
        external_user_id=user_id,
        series_name=series,
        total_activities=5,
        participated_activities=3,
        activities=mock_activities,
        query_time=current_time,
    )


# Future endpoints for external integrations can be added here:
# - @router.post("/submit-score") - Submit scores to external system
# - @router.get("/series-info") - Get series metadata
# - @router.get("/leaderboard") - Get leaderboard data
