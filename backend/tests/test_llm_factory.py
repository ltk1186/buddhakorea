from unittest.mock import Mock

from backend.app import main
from backend.app.llm import factory
from backend.app.llm.types import ChatModelRequest, LLMProviderConfig


def test_get_provider_for_model_routes_gemini_to_vertex():
    assert factory.get_provider_for_model("gemini-2.5-pro") == "gemini_vertex"


def test_get_provider_for_model_routes_gemini_to_google_genai_when_selected():
    assert (
        factory.get_provider_for_model(
            "gemini-2.5-pro",
            gemini_provider="google_genai",
        )
        == "gemini_google_genai"
    )


def test_get_provider_for_model_routes_claude_to_anthropic():
    assert factory.get_provider_for_model("claude-3-5-sonnet-20241022") == "anthropic"


def test_get_provider_for_model_routes_other_models_to_openai():
    assert factory.get_provider_for_model("gpt-4o-mini") == "openai"


def test_create_chat_llm_routes_gemini_to_vertex(monkeypatch):
    created = object()
    chat_vertex = Mock(return_value=created)
    monkeypatch.setattr("backend.app.llm.gemini_vertex.ChatVertexAI", chat_vertex)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gemini-2.5-pro",
            temperature=0.3,
            max_tokens=8192,
        ),
        LLMProviderConfig(
            gcp_project_id="project-123",
            gcp_location="asia-northeast3",
        ),
    )

    assert result is created
    chat_vertex.assert_called_once_with(
        model="gemini-2.5-pro",
        project="project-123",
        location="asia-northeast3",
        temperature=0.3,
        max_tokens=8192,
    )


def test_create_chat_llm_routes_streaming_fast_gemini(monkeypatch):
    created = object()
    chat_vertex = Mock(return_value=created)
    monkeypatch.setattr("backend.app.llm.gemini_vertex.ChatVertexAI", chat_vertex)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gemini-2.5-flash",
            temperature=0.3,
            max_tokens=8192,
            streaming=True,
        ),
        LLMProviderConfig(
            gcp_project_id="project-123",
            gcp_location="us-central1",
        ),
    )

    assert result is created
    chat_vertex.assert_called_once_with(
        model="gemini-2.5-flash",
        project="project-123",
        location="us-central1",
        temperature=0.3,
        max_tokens=8192,
        streaming=True,
    )


def test_create_chat_llm_routes_gemini_to_google_genai_when_selected(monkeypatch):
    created = object()
    chat_genai = Mock(return_value=created)
    monkeypatch.setattr(
        "backend.app.llm.gemini_google_genai.ChatGoogleGenerativeAI",
        chat_genai,
    )

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gemini-2.5-pro",
            temperature=0.3,
            max_tokens=4096,
            streaming=True,
        ),
        LLMProviderConfig(
            gemini_api_key="gemini-key",
            gemini_provider="google_genai",
        ),
    )

    assert result is created
    chat_genai.assert_called_once_with(
        model="gemini-2.5-pro",
        google_api_key="gemini-key",
        temperature=0.3,
        max_tokens=4096,
        streaming=True,
    )


def test_create_chat_llm_requires_gemini_key_for_google_genai_route(monkeypatch):
    chat_genai = Mock()
    monkeypatch.setattr(
        "backend.app.llm.gemini_google_genai.ChatGoogleGenerativeAI",
        chat_genai,
    )

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gemini-2.5-pro",
            temperature=0.3,
            max_tokens=4096,
        ),
        LLMProviderConfig(gemini_provider="google_genai"),
    )

    assert result is None
    chat_genai.assert_not_called()


def test_create_chat_llm_requires_anthropic_key_for_claude(monkeypatch):
    chat_anthropic = Mock()
    monkeypatch.setattr("backend.app.llm.anthropic.ChatAnthropic", chat_anthropic)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="claude-3-5-sonnet-20241022",
            temperature=0.3,
            max_tokens=2000,
        ),
        LLMProviderConfig(),
    )

    assert result is None
    chat_anthropic.assert_not_called()


def test_create_chat_llm_routes_claude_when_key_is_configured(monkeypatch):
    created = object()
    chat_anthropic = Mock(return_value=created)
    monkeypatch.setattr("backend.app.llm.anthropic.ChatAnthropic", chat_anthropic)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="claude-3-5-sonnet-20241022",
            temperature=0.2,
            max_tokens=8000,
        ),
        LLMProviderConfig(anthropic_api_key="anthropic-key"),
    )

    assert result is created
    chat_anthropic.assert_called_once_with(
        model="claude-3-5-sonnet-20241022",
        anthropic_api_key="anthropic-key",
        temperature=0.2,
        max_tokens=8000,
    )


def test_create_chat_llm_requires_openai_key_for_fallback(monkeypatch):
    chat_openai = Mock()
    monkeypatch.setattr("backend.app.llm.openai.ChatOpenAI", chat_openai)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2000,
        ),
        LLMProviderConfig(),
    )

    assert result is None
    chat_openai.assert_not_called()


def test_create_chat_llm_routes_openai_when_key_is_configured(monkeypatch):
    created = object()
    chat_openai = Mock(return_value=created)
    monkeypatch.setattr("backend.app.llm.openai.ChatOpenAI", chat_openai)

    result = factory.create_chat_llm(
        ChatModelRequest(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=1000,
        ),
        LLMProviderConfig(openai_api_key="openai-key"),
    )

    assert result is created
    chat_openai.assert_called_once_with(
        model="gpt-4o-mini",
        openai_api_key="openai-key",
        temperature=0.1,
        max_tokens=1000,
    )


def test_main_create_chat_llm_delegates_to_provider_factory(monkeypatch):
    created = object()
    delegated = Mock(return_value=created)
    monkeypatch.setattr(main, "create_provider_chat_llm", delegated)
    monkeypatch.setattr(main.config, "openai_api_key", "openai-key")
    monkeypatch.setattr(main.config, "anthropic_api_key", "anthropic-key")
    monkeypatch.setattr(main.config, "gemini_api_key", "gemini-key")
    monkeypatch.setattr(main.config, "gemini_provider", "google_genai")
    monkeypatch.setattr(main.config, "gcp_project_id", "project-123")
    monkeypatch.setattr(main.config, "gcp_location", "asia-northeast3")

    result = main.create_chat_llm(
        "gpt-4o-mini",
        temperature=0.1,
        max_tokens=1000,
        streaming=True,
    )

    assert result is created
    delegated.assert_called_once_with(
        ChatModelRequest(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=1000,
            streaming=True,
        ),
        LLMProviderConfig(
            openai_api_key="openai-key",
            anthropic_api_key="anthropic-key",
            gemini_api_key="gemini-key",
            gemini_provider="google_genai",
            gcp_project_id="project-123",
            gcp_location="asia-northeast3",
        ),
    )
