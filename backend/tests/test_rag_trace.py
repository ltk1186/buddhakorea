from backend.app.rag.prompts import NORMAL_PROMPT_ID
from backend.app.rag.trace import RetrievalConfigTrace, build_query_trace


def test_build_query_trace_includes_prompt_and_retrieval_metadata():
    retrieval = RetrievalConfigTrace(
        mode="sutra_filter",
        top_k=20,
        max_sources=5,
        detailed_mode=True,
        collection="cbeta",
        filter_type="sutra_id",
        filter_value="T01n0001",
        hyde_applied=True,
    )

    trace = build_query_trace(
        prompt_id=NORMAL_PROMPT_ID,
        retrieval=retrieval,
        response_mode="detailed",
        streaming=False,
        model="gemini-2.5-pro",
    )

    assert trace["prompt"]["id"] == "normal_v1"
    assert trace["prompt"]["version"] == "v1"
    assert trace["retrieval"]["mode"] == "sutra_filter"
    assert trace["retrieval"]["top_k"] == 20
    assert trace["retrieval"]["filter_value"] == "T01n0001"
    assert trace["response_mode"] == "detailed"
    assert trace["streaming"] is False
    assert trace["model"] == "gemini-2.5-pro"

