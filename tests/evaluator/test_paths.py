"""Evaluator storage path contract tests."""

from pathlib import Path

from evaluator.paths import get_data_dir, get_home_dir


def test_home_dir_respects_oscanner_home(monkeypatch, tmp_path):
    monkeypatch.setenv("OSCANNER_HOME", str(tmp_path / "oscanner-home"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert get_home_dir() == tmp_path / "oscanner-home"


def test_data_dir_specific_override_wins_over_oscanner_home(monkeypatch, tmp_path):
    monkeypatch.setenv("OSCANNER_HOME", str(tmp_path / "oscanner-home"))
    monkeypatch.setenv("OSCANNER_DATA_DIR", str(tmp_path / "explicit-data"))

    assert get_data_dir() == tmp_path / "explicit-data"
