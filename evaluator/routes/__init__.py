"""Route modules for FastAPI endpoints."""

from evaluator.routes import plugins, config, data, evaluation, batch, benchmark

__all__ = ["plugins", "config", "data", "evaluation", "batch", "benchmark"]
