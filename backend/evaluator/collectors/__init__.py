"""Data collectors for various platforms"""

from .github import GitHubCollector
from .gitee import GiteeCollector

__all__ = ["GitHubCollector", "GiteeCollector"]
