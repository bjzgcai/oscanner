"""
Pydantic schemas for Repository Runner
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """Status of a runner task"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RepoCloneRequest(BaseModel):
    """Request model for cloning a repository"""
    repo_url: str


class RepoMetadata(BaseModel):
    """Repository metadata"""
    repo_name: str
    default_branch: str
    latest_commit_id: str
    clone_path: str


class StreamEvent(BaseModel):
    """Server-sent event for streaming progress"""
    event: str
    data: Dict[str, Any]


class ExploreProgress(BaseModel):
    """Progress update for repository exploration"""
    status: TaskStatus
    message: str
    progress: Optional[int] = None


class TestResult(BaseModel):
    """Result of running a single test"""
    name: str
    status: str
    duration: Optional[float] = None
    output: Optional[str] = None


class TestSummary(BaseModel):
    """Summary of all test results"""
    total: int
    passed: int
    failed: int
    skipped: int
    score: int
    details: List[TestResult]
