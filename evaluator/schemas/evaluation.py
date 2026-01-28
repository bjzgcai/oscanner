"""Evaluation API response schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ScoresSchema(BaseModel):
    """Evaluation scores model."""

    # Six dimensions (legacy field names for backward compatibility)
    spec_quality: Optional[int] = Field(None, ge=0, le=100, description="AI Model Full-Stack & Trade-off score")
    cloud_architecture: Optional[int] = Field(None, ge=0, le=100, description="AI Native Architecture & Communication score")
    ai_engineering: Optional[int] = Field(None, ge=0, le=100, description="Cloud Native Engineering score")
    mastery_professionalism: Optional[int] = Field(None, ge=0, le=100, description="Open Source Collaboration score")

    # New standardized field names (2026 plugin)
    ai_fullstack: Optional[int] = Field(None, ge=0, le=100, description="AI Model Full-Stack & Trade-off")
    ai_architecture: Optional[int] = Field(None, ge=0, le=100, description="AI Native Architecture & Communication")
    cloud_native: Optional[int] = Field(None, ge=0, le=100, description="Cloud Native Engineering")
    open_source: Optional[int] = Field(None, ge=0, le=100, description="Open Source Collaboration")
    intelligent_dev: Optional[int] = Field(None, ge=0, le=100, description="Intelligent Development")
    leadership: Optional[int] = Field(None, ge=0, le=100, description="Engineering Leadership")

    reasoning: str = Field(..., description="Detailed reasoning and analysis in markdown format")

    class Config:
        extra = "allow"  # Allow additional fields from different plugins


class CommitsSummarySchema(BaseModel):
    """Summary statistics of analyzed commits."""

    total_additions: int = Field(0, ge=0, description="Total lines added across all commits")
    total_deletions: int = Field(0, ge=0, description="Total lines deleted across all commits")
    files_changed: int = Field(0, ge=0, description="Total number of files modified")
    languages: List[str] = Field(default_factory=list, description="Programming languages detected in commits")


class EvaluationSchema(BaseModel):
    """Engineer evaluation result."""

    # Core fields
    username: str = Field(..., description="Author username or alias")
    total_commits_analyzed: int = Field(..., ge=0, description="Number of commits analyzed in this run")
    files_loaded: int = Field(0, ge=0, description="Number of file diffs loaded for analysis")
    mode: str = Field("moderate", description="Evaluation mode (e.g., moderate, detailed)")

    # Evaluation results
    scores: ScoresSchema = Field(..., description="Dimensional scores and reasoning")
    commits_summary: CommitsSummarySchema = Field(..., description="Commit statistics summary")

    # Chunking metadata
    chunked: bool = Field(False, description="Whether evaluation used chunked processing")
    chunks_processed: int = Field(0, ge=0, description="Number of chunks processed if chunked=true")
    chunking_strategy: Optional[str] = Field(None, description="Chunking strategy used (e.g., parallel, sequential)")

    # Incremental evaluation tracking
    last_commit_sha: Optional[str] = Field(None, description="SHA of the most recent commit evaluated")
    total_commits_evaluated: int = Field(0, ge=0, description="Cumulative total commits evaluated (including previous runs)")
    new_commits_count: int = Field(0, ge=0, description="Number of new commits in this evaluation")
    evaluated_at: str = Field(..., description="ISO 8601 timestamp of evaluation")
    incremental: bool = Field(False, description="Whether this was an incremental evaluation")

    # Plugin metadata
    plugin: str = Field(..., description="Plugin ID used for evaluation")
    plugin_version: str = Field(..., description="Plugin version string")

    # Optional fields
    commit_ids: Optional[List[str]] = Field(None, description="List of commit IDs analyzed")

    class Config:
        extra = "allow"  # Allow additional plugin-specific fields


class EvaluationMetadata(BaseModel):
    """Metadata about the evaluation response."""

    cached: bool = Field(False, description="Whether the result was loaded from cache")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the response")
    source: Optional[str] = Field(None, description="Source of evaluation (e.g., merged_aliases, single_alias)")


class EvaluationResponseSchema(BaseModel):
    """Standard API response for evaluation endpoints."""

    success: bool = Field(..., description="Whether the evaluation succeeded")
    evaluation: EvaluationSchema = Field(..., description="Evaluation result data")
    metadata: EvaluationMetadata = Field(..., description="Response metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "evaluation": {
                    "username": "CarterWu",
                    "total_commits_analyzed": 50,
                    "files_loaded": 0,
                    "mode": "moderate",
                    "scores": {
                        "spec_quality": 28,
                        "cloud_architecture": 10,
                        "ai_engineering": 10,
                        "mastery_professionalism": 26,
                        "reasoning": "**主要优势**:\n- 用户在AI应用开发方面表现出色..."
                    },
                    "commits_summary": {
                        "total_additions": 385,
                        "total_deletions": 1,
                        "files_changed": 5,
                        "languages": ["gitignore", "js", "css", "html"]
                    },
                    "chunked": True,
                    "chunks_processed": 4,
                    "chunking_strategy": "parallel",
                    "last_commit_sha": "b5dd70db702701c59e16d57ba725c54cd359cdf8",
                    "total_commits_evaluated": 50,
                    "new_commits_count": 50,
                    "evaluated_at": "2026-01-25T11:43:47.360638",
                    "incremental": False,
                    "plugin": "zgc_ai_native_2026",
                    "plugin_version": "0.1.0"
                },
                "metadata": {
                    "cached": False,
                    "timestamp": "2026-01-25T11:43:47.360638"
                }
            }
        }
