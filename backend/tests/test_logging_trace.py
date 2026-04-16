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
