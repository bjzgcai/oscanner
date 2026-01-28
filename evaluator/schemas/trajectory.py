"""Growth trajectory schemas for tracking user development over time."""

from typing import List, Optional
from pydantic import BaseModel, Field
from .evaluation import EvaluationSchema


class CommitsRange(BaseModel):
    """Range of commits included in a checkpoint."""

    start_sha: str = Field(..., description="SHA of the oldest commit in this checkpoint")
    end_sha: str = Field(..., description="SHA of the newest commit in this checkpoint")
    commit_count: int = Field(..., ge=1, description="Number of commits in this checkpoint")


class TrajectoryCheckpoint(BaseModel):
    """A growth checkpoint representing evaluation of N commits."""

    checkpoint_id: int = Field(..., ge=1, description="Sequential checkpoint ID")
    created_at: str = Field(..., description="ISO 8601 timestamp when checkpoint was created")
    commits_range: CommitsRange = Field(..., description="Range of commits analyzed")
    evaluation: EvaluationSchema = Field(..., description="Full evaluation result for this checkpoint")
    repos_analyzed: Optional[List[str]] = Field(None, description="List of repo URLs analyzed")
    aliases_used: Optional[List[str]] = Field(None, description="Author aliases used in filtering")


class TrajectoryCache(BaseModel):
    """Complete growth trajectory data for a user."""

    username: str = Field(..., description="Primary username")
    repo_urls: List[str] = Field(..., description="Repository URLs being tracked")
    checkpoints: List[TrajectoryCheckpoint] = Field(default_factory=list, description="Historical checkpoints")
    last_synced_sha: Optional[str] = Field(None, description="SHA of most recent commit processed")
    last_synced_at: Optional[str] = Field(None, description="ISO 8601 timestamp of last sync")
    total_checkpoints: int = Field(0, ge=0, description="Total number of checkpoints created")


class TrajectoryResponse(BaseModel):
    """API response for trajectory analysis."""

    success: bool = Field(..., description="Whether the operation succeeded")
    trajectory: Optional[TrajectoryCache] = Field(None, description="Trajectory data")
    new_checkpoint_created: bool = Field(False, description="Whether a new checkpoint was created")
    message: str = Field(..., description="Human-readable message about the operation")
    commits_pending: Optional[int] = Field(None, description="Number of commits not yet forming a checkpoint")
