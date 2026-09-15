import json
import logging

from fastapi.testclient import TestClient

from research_agent.main import app
from research_agent.observability import (
    JsonTelemetryFormatter,
    log_event,
    reset_request_id,
    set_request_id,
)


def test_health_response_includes_application_request_id() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32


def test_caller_request_id_is_not_trusted() -> None:
    response = TestClient(app).get(
        "/health",
        headers={"X-Request-ID": "caller-controlled-value"},
    )

    assert response.headers["X-Request-ID"] != "caller-controlled-value"
    assert len(response.headers["X-Request-ID"]) == 32


def test_request_id_is_exposed_to_configured_browser_origin() -> None:
    response = TestClient(app).get(
        "/health",
        headers={"Origin": "https://marvinjb.dev"},
    )

    assert response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"


def test_json_formatter_contains_only_safe_operational_fields() -> None:
    token = set_request_id("request-123")
    try:
        record = logging.LogRecord(
            "research_agent.telemetry",
            logging.INFO,
            __file__,
            1,
            "research_worker_completed",
            (),
            None,
        )
        record.event_data = {
            "worker_id": "worker-1",
            "source_count": 4,
            "prompt": "must-not-appear",
            "api_key": "must-not-appear",
        }

        payload = json.loads(JsonTelemetryFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["event"] == "research_worker_completed"
    assert payload["request_id"] == "request-123"
    assert payload["worker_id"] == "worker-1"
    assert payload["source_count"] == 4
    assert "prompt" not in payload
    assert "api_key" not in payload


def test_log_event_discards_non_allowlisted_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def capture(message: str, *, extra: dict[str, object]) -> None:
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr("research_agent.observability.logger.info", capture)

    log_event(
        "provider_call_failed",
        component="tavily_search",
        error_category="timeout",
        provider_body="must-not-appear",
    )

    assert captured["message"] == "provider_call_failed"
    assert captured["extra"] == {
        "event_data": {
            "component": "tavily_search",
            "error_category": "timeout",
        }
    }
