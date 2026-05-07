import json

from evaluator.routes.trajectory import format_sse_event, router
from plugins.zgc_ai_native_2026.scan import extract_stream_delta


def test_format_sse_event_emits_named_json_event():
    assert format_sse_event("token", {"content": "hello"}) == (
        'event: token\n'
        'data: {"content":"hello"}\n\n'
    )


def test_extract_stream_delta_reads_openai_compatible_delta():
    line = "data: " + json.dumps({
        "choices": [
            {"delta": {"content": "partial text"}}
        ]
    })

    assert extract_stream_delta(line) == "partial text"


def test_extract_stream_delta_ignores_done_and_empty_lines():
    assert extract_stream_delta("data: [DONE]") is None
    assert extract_stream_delta("") is None


def test_regular_trajectory_stream_endpoint_is_registered():
    paths = {route.path for route in router.routes}

    assert "/api/trajectory/analyze_stream" in paths
