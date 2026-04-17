"""LangChain LCEL chain helpers for the Buddha Korea RAG runtime."""

from __future__ import annotations

from typing import Any

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableSerializable


def create_rag_chain(
    llm: BaseChatModel,
    retriever: BaseRetriever,
    prompt: PromptTemplate,
) -> RunnableSerializable[dict[str, Any], dict[str, Any]]:
    """Create the LCEL RAG chain used by the chat endpoints."""

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)


def invoke_rag_chain(
    chain: RunnableSerializable[dict[str, Any], dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    """Invoke an LCEL RAG chain while preserving the legacy public response shape."""

    result = chain.invoke({"input": query, "question": query})
    return {
        "result": result.get("answer", result.get("result", "")),
        "source_documents": result.get("context", result.get("source_documents", [])),
    }
