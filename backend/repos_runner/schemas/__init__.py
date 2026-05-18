"""
Pydantic schemas for Repository Runner
"""

from pydantic import BaseModel, Field, HttpUrl
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
    sha: Optional[str] = None  # Optional SHA to checkout after clone
    tag: Optional[str] = None  # Optional tag to checkout after clone (ignored if sha is set)
    clone_timeout: int = Field(default=300, gt=0)  # Seconds allowed for git clone/checkout


class RunAllRequest(BaseModel):
    """Request model for the combined clone → explore → test pipeline"""
    repo_url: str
    sha: Optional[str] = None
    tag: Optional[str] = None  # Optional tag to checkout (ignored if sha is set)
    tag_message: Optional[str] = None  # Merged feature requirements supplied by Courses
    skip_clone: bool = False    # Reuse existing clone
    skip_explore: bool = False  # Reuse existing REPO_OVERVIEW.md
    clone_timeout: int = Field(default=300, gt=0)    # Seconds allowed for git clone/checkout
    setup_timeout: int = Field(default=300, gt=0)    # Seconds per setup command
    test_timeout: int = Field(default=600, gt=0)     # Seconds per test command
    pipeline_timeout: float = Field(default=1800, gt=0)  # Seconds for the whole run-all pipeline


class BatchRunRequest(BaseModel):
    """Request model for running multiple repos concurrently (max 3 at a time)"""
    repos: List[RunAllRequest]
    max_concurrency: int = 3    # Max parallel pipelines (capped at 3)


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
