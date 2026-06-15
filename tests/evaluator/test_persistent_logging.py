import io

from backend.oscanner_logging import (
    _RotatingFileWriter,
    _TeeStream,
    configure_service_logging,
    get_log_dir,
    get_service_log_path,
    mask_known_secrets,
)


def test_log_dir_defaults_to_oscanner_home(monkeypatch, tmp_path):
    monkeypatch.setenv("OSCANNER_HOME", str(tmp_path))
    monkeypatch.delenv("OSCANNER_LOG_DIR", raising=False)

    assert get_log_dir() == tmp_path / "logs"
    assert get_service_log_path("Evaluator API") == tmp_path / "logs" / "Evaluator-API.log"


def test_log_dir_can_be_overridden(monkeypatch, tmp_path):
    custom_dir = tmp_path / "custom-logs"
    monkeypatch.setenv("OSCANNER_LOG_DIR", str(custom_dir))

    assert get_service_log_path("evaluator") == custom_dir / "evaluator.log"


def test_tee_stream_persists_masked_output(monkeypatch, tmp_path):
    monkeypatch.setenv("OSCANNER_LLM_API_KEY", "sk-testsecretvalue")
    log_path = tmp_path / "backend.log"
    original = io.StringIO()
    writer = _RotatingFileWriter(log_path, max_bytes=1024, backup_count=2)
    stream = _TeeStream(original, writer, log_path)

    stream.write("using sk-testsecretvalue\n")
    stream.flush()

    assert original.getvalue() == "using sk-testsecretvalue\n"
    assert log_path.read_text(encoding="utf-8") == "using sk-t...alue\n"


def test_mask_known_secrets_ignores_short_values(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "short")

    assert mask_known_secrets("token=short") == "token=short"


def test_configure_service_logging_can_be_disabled(monkeypatch):
    monkeypatch.setenv("OSCANNER_PERSIST_LOGS", "0")

    assert configure_service_logging("evaluator") is None
