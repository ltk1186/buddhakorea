from unittest.mock import Mock

from backend.app import main


def test_create_chat_llm_routes_gemini_to_vertex(monkeypatch):
    created = object()
    chat_vertex = Mock(return_value=created)
    monkeypatch.setattr(main, "ChatVertexAI", chat_vertex)
    monkeypatch.setattr(main.config, "gcp_project_id", "project-123")
    monkeypatch.setattr(main.config, "gcp_location", "asia-northeast3")

    result = main.create_chat_llm(
        "gemini-2.5-pro",
        temperature=0.3,
        max_tokens=8192,
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
    monkeypatch.setattr(main, "ChatVertexAI", chat_vertex)
    monkeypatch.setattr(main.config, "gcp_project_id", "project-123")
    monkeypatch.setattr(main.config, "gcp_location", "us-central1")

    result = main.create_chat_llm(
        "gemini-2.5-flash",
        temperature=0.3,
        max_tokens=8192,
        streaming=True,
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


def test_create_chat_llm_requires_anthropic_key_for_claude(monkeypatch):
    chat_anthropic = Mock()
    monkeypatch.setattr(main, "ChatAnthropic", chat_anthropic)
    monkeypatch.setattr(main.config, "anthropic_api_key", None)

    result = main.create_chat_llm(
        "claude-3-5-sonnet-20241022",
        temperature=0.3,
        max_tokens=2000,
    )

    assert result is None
    chat_anthropic.assert_not_called()


def test_create_chat_llm_routes_claude_when_key_is_configured(monkeypatch):
    created = object()
    chat_anthropic = Mock(return_value=created)
    monkeypatch.setattr(main, "ChatAnthropic", chat_anthropic)
    monkeypatch.setattr(main.config, "anthropic_api_key", "anthropic-key")

    result = main.create_chat_llm(
        "claude-3-5-sonnet-20241022",
        temperature=0.2,
        max_tokens=8000,
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
    monkeypatch.setattr(main, "ChatOpenAI", chat_openai)
    monkeypatch.setattr(main.config, "openai_api_key", None)

    result = main.create_chat_llm(
        "gpt-4o-mini",
        temperature=0.3,
        max_tokens=2000,
    )

    assert result is None
    chat_openai.assert_not_called()


def test_create_chat_llm_routes_openai_when_key_is_configured(monkeypatch):
    created = object()
    chat_openai = Mock(return_value=created)
    monkeypatch.setattr(main, "ChatOpenAI", chat_openai)
    monkeypatch.setattr(main.config, "openai_api_key", "openai-key")

    result = main.create_chat_llm(
        "gpt-4o-mini",
        temperature=0.1,
        max_tokens=1000,
    )

    assert result is created
    chat_openai.assert_called_once_with(
        model="gpt-4o-mini",
        openai_api_key="openai-key",
        temperature=0.1,
        max_tokens=1000,
    )


def test_create_rag_chain_uses_lcel_factories(monkeypatch):
    llm = object()
    retriever = object()
    prompt = object()
    document_chain = object()
    rag_chain = object()
    create_stuff_documents_chain = Mock(return_value=document_chain)
    create_retrieval_chain = Mock(return_value=rag_chain)
    monkeypatch.setattr(
        main,
        "create_stuff_documents_chain",
        create_stuff_documents_chain,
    )
    monkeypatch.setattr(main, "create_retrieval_chain", create_retrieval_chain)

    result = main.create_rag_chain(llm, retriever, prompt)

    assert result is rag_chain
    create_stuff_documents_chain.assert_called_once_with(llm, prompt)
    create_retrieval_chain.assert_called_once_with(retriever, document_chain)


def test_invoke_rag_chain_uses_lcel_payload_and_preserves_response_shape():
    source_documents = [object()]
    chain = Mock()
    chain.invoke.return_value = {
        "answer": "ok",
        "context": source_documents,
        "input": "사성제란 무엇입니까?",
    }

    result = main.invoke_rag_chain(chain, "사성제란 무엇입니까?")

    assert result == {"result": "ok", "source_documents": source_documents}
    chain.invoke.assert_called_once_with(
        {
            "input": "사성제란 무엇입니까?",
            "question": "사성제란 무엇입니까?",
        }
    )


def test_invoke_rag_chain_accepts_legacy_result_keys():
    source_documents = [object()]
    chain = Mock()
    chain.invoke.return_value = {
        "result": "legacy ok",
        "source_documents": source_documents,
    }

    result = main.invoke_rag_chain(chain, "무상")

    assert result == {"result": "legacy ok", "source_documents": source_documents}
