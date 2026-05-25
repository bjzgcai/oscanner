from pathlib import Path


WEBAPP = Path(__file__).resolve().parents[2] / "frontend" / "webapp"


def test_validation_results_renders_justice_profile():
    source = (WEBAPP / "components" / "validation" / "ValidationResults.tsx").read_text(
        encoding="utf-8"
    )

    assert "justice_profile" in source
    assert "justice.check" in source


def test_validation_controls_use_dataset_categories():
    runner_source = (WEBAPP / "components" / "validation" / "ValidationRunner.tsx").read_text(
        encoding="utf-8"
    )
    overview_source = (WEBAPP / "components" / "validation" / "DatasetOverview.tsx").read_text(
        encoding="utf-8"
    )

    assert "setCategories" in runner_source
    assert "setCategories" in overview_source
    assert 'value="dimension_specialist"' not in runner_source
    assert 'value="dimension_specialist"' not in overview_source
