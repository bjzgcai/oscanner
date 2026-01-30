"""
Engineer Capability Assessment System

A comprehensive system for evaluating engineer capabilities based on
GitHub and Gitee activity analysis.
"""

import sys
from pathlib import Path

# Add backend directory to Python path to allow 'evaluator' imports
# This must be done before any other imports that use 'evaluator' as a top-level package
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from .core import EngineerEvaluator, EvaluationResult

__version__ = "0.1.0"
__all__ = ["EngineerEvaluator", "EvaluationResult"]
