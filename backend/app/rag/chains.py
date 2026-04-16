"""LangChain LCEL chain helpers for the Buddha Korea RAG runtime."""

from __future__ import annotations

from typing import Any, Dict

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate


def create_rag_chain(llm: Any, retriever: Any, prompt: PromptTemplate) -> Any:
    """Create the LCEL RAG chain used by the chat endpoints."""

    document_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(retriever, document_chain)


def invoke_rag_chain(chain: Any, query: str) -> Dict[str, Any]:
    """Invoke an LCEL RAG chain while preserving the legacy response shape."""

    result = chain.invoke({"input": query, "question": query})
    return {
        "result": result.get("answer", result.get("result", "")),
        "source_documents": result.get("context", result.get("source_documents", [])),
    }
