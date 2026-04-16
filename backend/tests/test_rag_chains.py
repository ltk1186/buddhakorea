from unittest.mock import Mock

from backend.app.rag import chains


def test_create_rag_chain_uses_lcel_factories(monkeypatch):
    llm = object()
    retriever = object()
    prompt = object()
    document_chain = object()
    rag_chain = object()
    create_stuff_documents_chain = Mock(return_value=document_chain)
    create_retrieval_chain = Mock(return_value=rag_chain)
    monkeypatch.setattr(
        chains,
        "create_stuff_documents_chain",
        create_stuff_documents_chain,
    )
    monkeypatch.setattr(chains, "create_retrieval_chain", create_retrieval_chain)

    result = chains.create_rag_chain(llm, retriever, prompt)

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

    result = chains.invoke_rag_chain(chain, "사성제란 무엇입니까?")

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

    result = chains.invoke_rag_chain(chain, "무상")

    assert result == {"result": "legacy ok", "source_documents": source_documents}
