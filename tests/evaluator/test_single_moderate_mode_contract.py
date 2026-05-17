import importlib.util
import inspect
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_plugin(plugin_id: str):
    scan_path = PROJECT_ROOT / "plugins" / plugin_id / "scan" / "__init__.py"
    spec = importlib.util.spec_from_file_location(f"test_{plugin_id}_single_mode", scan_path)
    plugin = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(plugin)
    return plugin


@pytest.mark.parametrize("plugin_id", ["zgc_simple", "zgc_ai_native_2026"])
def test_plugin_factory_and_constructor_do_not_accept_mode(plugin_id):
    plugin = _load_plugin(plugin_id)

    assert "mode" not in inspect.signature(plugin.create_commit_evaluator).parameters
    assert "mode" not in inspect.signature(plugin.CommitEvaluatorModerate).parameters

    with pytest.raises(TypeError):
        plugin.create_commit_evaluator(
            data_dir="",
            api_key="test-key",
            model="deepseek/deepseek-v4-pro",
            mode="moderate",
        )
