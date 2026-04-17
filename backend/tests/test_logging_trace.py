from datetime import datetime

from backend.app import qa_logger, usage_tracker


class _BoundLogger:
    def __init__(self, sink):
        self.sink = sink

    def info(self, message):
        self.sink["message"] = message


def test_log_token_usage_includes_trace(monkeypatch):
    captured = {}

    def fake_bind(**kwargs):
        captured.update(kwargs)
        return _BoundLogger(captured)

    monkeypatch.setattr(usage_tracker.logger, "bind", fake_bind)

    usage_tracker.log_token_usage(
        query="질문",
        response="응답",
        input_tokens=10,
        output_tokens=5,
        model="gemini-2.5-pro",
        trace={
            "prompt": {"id": "normal_v1"},
            "retrieval": {"mode": "default"},
            "provider": "gemini_vertex",
        },
    )

    assert captured["usage"]["trace"]["prompt"]["id"] == "normal_v1"
    assert captured["usage"]["trace"]["retrieval"]["mode"] == "default"
    assert captured["usage"]["trace"]["provider"] == "gemini_vertex"
    assert captured["message"] == "Token usage logged"


def test_log_qa_pair_includes_trace(monkeypatch):
    captured = {}

    def fake_bind(**kwargs):
        captured.update(kwargs)
        return _BoundLogger(captured)

    monkeypatch.setattr(qa_logger.logger, "bind", fake_bind)

    qa_logger.log_qa_pair(
        query="질문",
        response="응답",
        trace={
            "prompt": {"id": "normal_v1"},
            "retrieval": {"mode": "default"},
            "provider": "gemini_vertex",
        },
    )

    assert captured["qa"]["trace"]["prompt"]["id"] == "normal_v1"
    assert captured["qa"]["trace"]["retrieval"]["mode"] == "default"
    assert captured["qa"]["trace"]["provider"] == "gemini_vertex"
    assert captured["message"] == "Q&A pair logged"


def test_analyze_observability_messages_derives_cache_and_cost_metrics():
    rows = [
        (datetime.fromisoformat("2026-04-17T10:00:00+00:00"), 1200, 1000, "gemini-2.5-pro", "normal"),
        (datetime.fromisoformat("2026-04-17T11:00:00+00:00"), 800, 0, "gemini-2.5-pro", "cached"),
    ]

    stats = usage_tracker.analyze_observability_messages(rows, days=7)

    assert stats["metrics_source"] == "database"
    assert stats["latency_metrics_available"] is True
    assert stats["cache_metrics_available"] is True
    assert stats["cost_metrics_available"] is True
    assert stats["cost_metrics_estimated"] is True
    assert stats["total_queries"] == 2
    assert stats["cache_queries_sample"] == 1
    assert stats["cache_hit_rate"] == 50.0
    assert stats["queries_with_cost"] == 1
    assert stats["avg_latency_ms"] == 1000
    assert stats["by_day"]["2026-04-17"]["cached_queries"] == 1
    assert stats["by_day"]["2026-04-17"]["cache_hit_rate"] == 50.0
