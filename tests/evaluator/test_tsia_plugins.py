import inspect
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluator.plugin_registry import discover_plugins, load_scan_module


@pytest.mark.parametrize(
    ("plugin_id", "expected_keys"),
    [
        (
            "tsia057_ai_agent_engineer_2026",
            {"p1_scenario_requirements", "d4_agent_orchestration", "m1_security_compliance"},
        ),
        (
            "tsia058_youth_ai_innovation_2026",
            {"cognition_ai_literacy", "application_generative_ai", "responsibility_ethics_risk"},
        ),
    ],
)
def test_tsia_plugins_are_discoverable_and_define_standard_dimensions(plugin_id, expected_keys):
    discovered = {meta.plugin_id for meta, _ in discover_plugins()}
    assert plugin_id in discovered

    _meta, scan_mod, _scan_path = load_scan_module(plugin_id)
    evaluator = scan_mod.create_commit_evaluator(data_dir="", api_key="test-key", model="test-model")

    assert len(evaluator.dimensions) == 12
    assert expected_keys.issubset(set(evaluator.dimensions))
    assert set(evaluator.dimensions) == set(evaluator.dimension_instructions)


def test_tsia_plugin_factories_reject_legacy_mode_argument():
    for plugin_id in ["tsia057_ai_agent_engineer_2026", "tsia058_youth_ai_innovation_2026"]:
        _meta, scan_mod, _scan_path = load_scan_module(plugin_id)
        assert "mode" not in inspect.signature(scan_mod.create_commit_evaluator).parameters
        assert "mode" not in inspect.signature(scan_mod.CommitEvaluatorModerate).parameters
        with pytest.raises(TypeError):
            scan_mod.create_commit_evaluator(
                data_dir="",
                api_key="test-key",
                model="test-model",
                mode="moderate",
            )
