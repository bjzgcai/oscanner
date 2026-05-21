"""Runner grading rubric defaults."""

from pathlib import Path


def _ai_native_rubric_path() -> Path:
    return Path(__file__).resolve().parents[2] / "plugins" / "zgc_ai_native_2026" / "rubric.md"


def load_default_grading_rubric() -> str:
    """Load the shared AI-Native 2026 rubric used by evaluator and runner."""
    return _ai_native_rubric_path().read_text(encoding="utf-8").strip()


DEFAULT_GRADING_RUBRIC = load_default_grading_rubric()


def normalize_grading_rubric(value: str | None) -> str:
    """Return the supplied rubric or the nonempty runner default."""
    rubric = str(value or "").strip()
    return rubric or DEFAULT_GRADING_RUBRIC
