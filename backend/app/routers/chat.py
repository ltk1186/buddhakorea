"""Public chat routers."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .. import database
from ..api_schemas import ChatRequest, ChatResponse, CollectionInfo, HealthResponse, SourceDocument
from ..chat_history_service import save_chat_to_db
from ..dependencies import get_current_user_optional
from ..models.user import User
from ..qa_logger import log_qa_pair
from ..quota import check_quota, get_client_ip, increment_usage
from ..rag.prompts import (
    DETAILED_PROMPT_ID,
    NORMAL_PROMPT_ID,
    STREAMING_DETAILED_PROMPT_ID,
    STREAMING_NORMAL_PROMPT_ID,
    SUTRA_FILTER_DETAILED_PROMPT_ID,
    SUTRA_FILTER_PROMPT_ID,
    TRADITION_FILTER_DETAILED_PROMPT_ID,
    TRADITION_FILTER_PROMPT_ID,
    build_prompt,
)
from ..rag.trace import RetrievalConfigTrace, build_query_trace
from ..tradition_normalizer import normalize_tradition
from ..usage_tracker import log_token_usage
try:
    from rag.buddhist_thesaurus import expand_query as expand_buddhist_terms
except ModuleNotFoundError:  # pragma: no cover - package path differs between runtime and tests
    from ...rag.buddhist_thesaurus import expand_query as expand_buddhist_terms


def create_chat_router(
    *,
    config: Any,
    app_state: Any,
    logger: Any,
    sutra_cache: Any,
    check_cached_response_fn: Any,
    create_or_get_session_fn: Any,
    get_session_context_fn: Any,
    update_session_fn: Any,
    create_chat_llm_fn: Any,
    extract_token_usage_fn: Any,
    invoke_rag_chain_fn: Any,
    create_rag_chain_fn: Any,
    get_provider_for_model_fn: Any,
) -> APIRouter:
    router = APIRouter(tags=["chat"])

    @router.get("/api/health", response_model=HealthResponse)
    async def health_check():
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            chroma_connected=app_state.chroma_client is not None,
            llm_configured=app_state.llm is not None,
        )

    @router.get("/api/collections", response_model=list[CollectionInfo])
    async def list_collections():
        if not app_state.chroma_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB not connected. Run embedding script first.",
            )

        collections = []
        try:
            all_collections = app_state.chroma_client.list_collections()
            for coll in all_collections:
                collections.append(
                    CollectionInfo(
                        name=coll.name,
                        document_count=coll.count(),
                        language="multilingual",
                        description=f"Buddhist texts collection: {coll.name}",
                    )
                )
        except Exception as exc:
            logger.error(f"Error listing collections: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )

        return collections

    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        http_request: Request,
        db: AsyncSession = Depends(database.get_db),
        user: Optional[User] = Depends(get_current_user_optional),
    ):
        start_time = time.time()
        await check_quota(db, http_request, user)

        if not app_state.qa_chain:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RAG system not initialized. Ensure ChromaDB has embedded documents.",
            )

        client_ip = get_client_ip(http_request)
        user_info = f"user={user.id}" if user else f"ip={client_ip}"
        logger.info(f"Query from {user_info}: {request.query[:100]}...")

        if not request.is_followup:
            cached_response = check_cached_response_fn(request.query)
            if cached_response:
                latency_ms = int((time.time() - start_time) * 1000)
                cached_sources = [
                    SourceDocument(**source) if isinstance(source, dict) else source
                    for source in cached_response.get("sources", [])
                ]
                session_id = create_or_get_session_fn(request.session_id)
                await increment_usage(db, http_request, user, tokens=0)
                cached_trace = build_query_trace(
                    prompt_id=NORMAL_PROMPT_ID,
                    retrieval=RetrievalConfigTrace(
                        mode="cache",
                        top_k=0,
                        max_sources=request.max_sources,
                        detailed_mode=False,
                        collection=request.collection,
                    ),
                    response_mode="cached",
                    streaming=False,
                    model=cached_response.get("model", config.llm_model),
                    provider=get_provider_for_model_fn(
                        cached_response.get("model", config.llm_model),
                        gemini_provider=config.gemini_provider,
                    ),
                )
                update_session_fn(
                    session_id=session_id,
                    user_message=request.query,
                    assistant_message=cached_response["response"],
                    context_chunks=cached_sources,
                    metadata={
                        "response_mode": "cached",
                        "query_trace": cached_trace,
                    },
                )
                updated_context = get_session_context_fn(session_id)
                conversation_depth = updated_context["conversation_depth"]
                log_token_usage(
                    query=request.query,
                    response=cached_response["response"],
                    input_tokens=int(estimated_tokens * 0.85),
                    output_tokens=int(estimated_tokens * 0.15),
                    model=cached_response.get("model", config.llm_model),
                    mode="cached",
                    session_id=session_id,
                    latency_ms=latency_ms,
                    from_cache=True,
                    trace=cached_trace,
                )
                log_qa_pair(
                    query=request.query,
                    response=cached_response["response"],
                    session_id=session_id,
                    model=cached_response.get("model", config.llm_model),
                    sources=[
                        source.text_id if isinstance(source, SourceDocument) else source.get("text_id", "")
                        for source in cached_sources[: request.max_sources]
                    ],
                    input_tokens=int(estimated_tokens * 0.85),
                    output_tokens=int(estimated_tokens * 0.15),
                    latency_ms=latency_ms,
                    from_cache=True,
                    trace=cached_trace,
                )
                await save_chat_to_db(
                    db=db,
                    session_uuid=session_id,
                    user_id=user.id if user else None,
                    user_message=request.query,
                    assistant_message=cached_response["response"],
                    metadata={
                        "model": cached_response.get("model", config.llm_model),
                        "sources_count": len(cached_sources[: request.max_sources]),
                        "sources": cached_sources[: request.max_sources],
                        "response_mode": "cached",
                        "latency_ms": latency_ms,
                        "tokens_used": estimated_tokens,
                        "query_trace": cached_trace,
                    },
                )
                return ChatResponse(
                    response=cached_response["response"],
                    sources=cached_sources[: request.max_sources],
                    model=cached_response.get("model", config.llm_model),
                    latency_ms=latency_ms,
                    collection=request.collection,
                    session_id=session_id,
                    can_followup=True,
                    conversation_depth=conversation_depth,
                    from_cache=True,
                )

        session_id = create_or_get_session_fn(request.session_id)
        session_context = get_session_context_fn(session_id)
        is_followup = request.is_followup and len(session_context["messages"]) > 0
        if is_followup:
            logger.info(f"Follow-up question (depth: {session_context['conversation_depth'] + 1})")

        try:
            query = expand_buddhist_terms(request.query)
            logger.debug(f"Buddhist term expansion: {request.query} -> {query}")

            if app_state.hyde_expander:
                expanded_query = app_state.hyde_expander.expand_query(query, weight_original=config.hyde_weight)
                logger.debug(f"HyDE expansion: {query[:50]}... -> {expanded_query[:100]}...")
                query = expanded_query

            detailed_llm = None
            detailed_k = 20
            if request.detailed_mode:
                logger.info("Detailed mode activated - using extended configuration")
                detailed_max_tokens = 8192 if "gemini" in config.llm_model.lower() else 8000
                detailed_llm = create_chat_llm_fn(
                    config.llm_model,
                    temperature=0.3,
                    max_tokens=detailed_max_tokens,
                )

            tradition_filter_normalized = None
            tradition_sutra_ids = None
            if request.tradition_filter:
                tradition_filter_normalized = normalize_tradition(request.tradition_filter)
                logger.info(
                    f"Tradition filter: {request.tradition_filter} -> normalized to: {tradition_filter_normalized}"
                )
                try:
                    cache_data = await sutra_cache.get_data()
                    summaries = cache_data.get("summaries", {})
                    tradition_sutra_ids = []
                    for sutra_id, source in summaries.items():
                        raw_trad = source.get("tradition", "")
                        normalized_trad = normalize_tradition(raw_trad)
                        if normalized_trad == tradition_filter_normalized:
                            tradition_sutra_ids.append(sutra_id)
                    logger.info(
                        f"Found {len(tradition_sutra_ids)} sutras for tradition: {tradition_filter_normalized}"
                    )
                except Exception as exc:
                    logger.warning(f"Failed to get tradition sutra list: {exc}")
                    tradition_sutra_ids = None

            response_mode = "detailed" if request.detailed_mode else "normal"
            if request.sutra_filter:
                logger.info(f"Applying sutra filter: {request.sutra_filter}")
                retrieval_k = (detailed_k * 2) if request.detailed_mode else (config.top_k_retrieval * 2)
                filtered_retriever = app_state.vectorstore.as_retriever(
                    search_kwargs={"k": retrieval_k, "filter": {"sutra_id": request.sutra_filter}}
                )
                prompt_id = SUTRA_FILTER_DETAILED_PROMPT_ID if request.detailed_mode else SUTRA_FILTER_PROMPT_ID
                retrieval_trace = RetrievalConfigTrace(
                    mode="sutra_filter",
                    top_k=retrieval_k,
                    max_sources=request.max_sources,
                    detailed_mode=request.detailed_mode,
                    collection=request.collection,
                    filter_type="sutra_id",
                    filter_value=request.sutra_filter,
                    hyde_applied=bool(app_state.hyde_expander),
                )
                filtered_qa_chain = create_rag_chain_fn(
                    detailed_llm if detailed_llm else app_state.llm,
                    filtered_retriever,
                    build_prompt(prompt_id),
                )
                result = invoke_rag_chain_fn(filtered_qa_chain, query)
                logger.info(f"Filtered query completed for sutra: {request.sutra_filter}")
            elif tradition_sutra_ids and len(tradition_sutra_ids) > 0:
                logger.info(
                    f"Applying tradition filter: {tradition_filter_normalized} ({len(tradition_sutra_ids)} sutras)"
                )
                retrieval_k = (detailed_k * 2) if request.detailed_mode else (config.top_k_retrieval * 2)
                filtered_retriever = app_state.vectorstore.as_retriever(
                    search_kwargs={"k": retrieval_k, "filter": {"sutra_id": {"$in": tradition_sutra_ids}}}
                )
                prompt_id = (
                    TRADITION_FILTER_DETAILED_PROMPT_ID
                    if request.detailed_mode
                    else TRADITION_FILTER_PROMPT_ID
                )
                retrieval_trace = RetrievalConfigTrace(
                    mode="tradition_filter",
                    top_k=retrieval_k,
                    max_sources=request.max_sources,
                    detailed_mode=request.detailed_mode,
                    collection=request.collection,
                    filter_type="tradition",
                    filter_value=tradition_filter_normalized,
                    filter_sutra_count=len(tradition_sutra_ids),
                    hyde_applied=bool(app_state.hyde_expander),
                )
                tradition_qa_chain = create_rag_chain_fn(
                    detailed_llm if detailed_llm else app_state.llm,
                    filtered_retriever,
                    build_prompt(prompt_id, tradition=tradition_filter_normalized),
                )
                result = invoke_rag_chain_fn(tradition_qa_chain, query)
                logger.info(f"Tradition-filtered query completed: {tradition_filter_normalized}")
            elif request.detailed_mode:
                logger.info("Running detailed mode query without sutra filter")
                detailed_retriever = app_state.vectorstore.as_retriever(search_kwargs={"k": detailed_k})
                prompt_id = DETAILED_PROMPT_ID
                retrieval_trace = RetrievalConfigTrace(
                    mode="detailed",
                    top_k=detailed_k,
                    max_sources=request.max_sources,
                    detailed_mode=True,
                    collection=request.collection,
                    hyde_applied=bool(app_state.hyde_expander),
                )
                detailed_qa_chain = create_rag_chain_fn(detailed_llm, detailed_retriever, build_prompt(prompt_id))
                result = invoke_rag_chain_fn(detailed_qa_chain, query)
                logger.info("Detailed query completed")
            else:
                prompt_id = NORMAL_PROMPT_ID
                retrieval_trace = RetrievalConfigTrace(
                    mode="default",
                    top_k=config.top_k_retrieval,
                    max_sources=request.max_sources,
                    detailed_mode=False,
                    collection=request.collection,
                    hyde_applied=bool(app_state.hyde_expander),
                )
                result = invoke_rag_chain_fn(app_state.qa_chain, query)

            query_trace = build_query_trace(
                prompt_id=prompt_id,
                retrieval=retrieval_trace,
                response_mode=response_mode,
                streaming=False,
                model=config.llm_model,
                provider=get_provider_for_model_fn(config.llm_model, gemini_provider=config.gemini_provider),
            )

            response_text = result["result"]
            source_docs = result.get("source_documents", [])

            try:
                cache_data = await sutra_cache.get_data()
                summaries = cache_data.get("summaries", {})
            except Exception:
                summaries = {}

            sources = []
            seen_sutras = set()
            for doc in source_docs[: request.max_sources]:
                metadata = doc.metadata
                sutra_id = metadata.get("sutra_id", "N/A")
                if sutra_id in seen_sutras:
                    continue
                seen_sutras.add(sutra_id)
                cached_info = summaries.get(sutra_id, {})
                title = cached_info.get("title_ko") or metadata.get("title_ko") or metadata.get("title", sutra_id)
                sources.append(
                    SourceDocument(
                        title=title,
                        text_id=sutra_id,
                        excerpt=doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content,
                        metadata=metadata,
                    )
                )

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Response generated in {latency_ms}ms with {len(sources)} sources")

            update_session_fn(
                session_id=session_id,
                user_message=request.query,
                assistant_message=response_text,
                context_chunks=source_docs,
                metadata={
                    "detailed_mode": request.detailed_mode,
                    "sutra_filter": request.sutra_filter,
                    "tradition_filter": tradition_filter_normalized,
                    "is_followup": is_followup,
                    "query_trace": query_trace,
                },
            )

            updated_context = get_session_context_fn(session_id)
            conversation_depth = updated_context["conversation_depth"]

            token_usage = extract_token_usage_fn(result, request.query, config.llm_model)
            log_token_usage(
                query=request.query,
                response=response_text,
                input_tokens=token_usage["input_tokens"],
                output_tokens=token_usage["output_tokens"],
                model=config.llm_model,
                mode=response_mode,
                session_id=session_id,
                latency_ms=latency_ms,
                from_cache=False,
                trace=query_trace,
            )

            source_ids = []
            for source in sources:
                if isinstance(source, SourceDocument):
                    source_ids.append(source.text_id)
                elif isinstance(source, dict):
                    source_ids.append(source.get("source_id", source.get("text_id", "")))
                else:
                    source_ids.append(str(source))

            log_qa_pair(
                query=request.query,
                response=response_text,
                detailed_mode=request.detailed_mode,
                sutra_filter=request.sutra_filter,
                session_id=session_id,
                model=config.llm_model,
                sources=source_ids,
                input_tokens=token_usage["input_tokens"],
                output_tokens=token_usage["output_tokens"],
                latency_ms=latency_ms,
                from_cache=False,
                trace=query_trace,
            )

            total_tokens = token_usage["input_tokens"] + token_usage["output_tokens"]
            await increment_usage(db, http_request, user, tokens=total_tokens)
            await save_chat_to_db(
                db=db,
                session_uuid=session_id,
                user_id=user.id if user else None,
                user_message=request.query,
                assistant_message=response_text,
                metadata={
                    "model": config.llm_model,
                    "sources_count": len(sources),
                    "sources": sources,
                    "response_mode": response_mode,
                    "latency_ms": latency_ms,
                    "tokens_used": total_tokens,
                    "query_trace": query_trace,
                },
            )
            return ChatResponse(
                response=response_text,
                sources=sources,
                model=config.llm_model,
                latency_ms=latency_ms,
                collection=request.collection,
                session_id=session_id,
                can_followup=True,
                conversation_depth=conversation_depth,
            )
        except Exception as exc:
            logger.error(f"Error processing chat request: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating response: {str(exc)}",
            )

    @router.post("/api/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        http_request: Request,
        db: AsyncSession = Depends(database.get_db),
        user: Optional[User] = Depends(get_current_user_optional),
    ):
        start_time = time.time()
        try:
            await check_quota(db, http_request, user)
        except HTTPException as exc:
            async def quota_error():
                error_detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
                yield f"data: {json.dumps({'type': 'error', 'code': 'quota_exceeded', **error_detail})}\n\n"

            return StreamingResponse(quota_error(), media_type="text/event-stream")

        session_uuid = create_or_get_session_fn(request.session_id)
        user_id = user.id if user else None
        client_ip = get_client_ip(http_request)

        if not app_state.vectorstore:
            async def system_error():
                yield f"data: {json.dumps({'type': 'error', 'message': 'RAG system not initialized'})}\n\n"

            return StreamingResponse(system_error(), media_type="text/event-stream")

        user_info = f"user={user_id}" if user_id else f"ip={client_ip}"
        logger.info(f"[Stream] Query from {user_info}: {request.query[:100]}...")

        async def generate():
            try:
                yield f"data: {json.dumps({'type': 'stage', 'stage': 'searching', 'message': '문헌 검색 중...'})}\n\n"
                await asyncio.sleep(0.1)

                is_detailed = request.detailed_mode
                retrieval_k = config.top_k_retrieval if is_detailed else config.top_k_retrieval_fast
                llm = app_state.llm if is_detailed else (app_state.llm_fast or app_state.llm)
                model_name = config.llm_model if is_detailed else config.llm_model_fast

                logger.info(
                    f"[Stream] Mode: {'detailed' if is_detailed else 'normal'}, k={retrieval_k}, model={model_name}"
                )

                query = expand_buddhist_terms(request.query)
                logger.info(f"[Stream] Buddhist term expansion: {request.query} -> {query}")

                if app_state.hyde_expander and not is_detailed:
                    query = app_state.hyde_expander.expand_query(query, weight_original=config.hyde_weight)

                search_kwargs = {"k": retrieval_k}
                tradition_sutra_ids = None
                tradition_filter_normalized = None
                if request.tradition_filter:
                    tradition_filter_normalized = normalize_tradition(request.tradition_filter)
                    logger.info(f"[Stream] Tradition filter: {request.tradition_filter} -> {tradition_filter_normalized}")
                    try:
                        cache_data = await sutra_cache.get_data()
                        summaries = cache_data.get("summaries", {})
                        tradition_sutra_ids = []
                        for sutra_id, source in summaries.items():
                            raw_trad = source.get("tradition", "")
                            normalized_trad = normalize_tradition(raw_trad)
                            if normalized_trad == tradition_filter_normalized:
                                tradition_sutra_ids.append(sutra_id)
                        logger.info(
                            f"[Stream] Found {len(tradition_sutra_ids)} sutras for tradition: {tradition_filter_normalized}"
                        )
                    except Exception as exc:
                        logger.warning(f"[Stream] Failed to get tradition sutra list: {exc}")

                logger.info(f"[Stream] Received sutra_filter: {request.sutra_filter}")
                logger.info(f"[Stream] Received tradition_filter: {request.tradition_filter}")

                if request.sutra_filter:
                    search_kwargs["filter"] = {"sutra_id": request.sutra_filter}
                    logger.info(f"[Stream] Applying sutra filter: {request.sutra_filter}")
                elif tradition_sutra_ids and len(tradition_sutra_ids) > 0:
                    search_kwargs["filter"] = {"sutra_id": {"$in": tradition_sutra_ids}}
                    logger.info(f"[Stream] Applying tradition filter with {len(tradition_sutra_ids)} sutras")
                else:
                    logger.info("[Stream] No filter applied - searching all documents")

                logger.info(f"[Stream] Final search_kwargs: {search_kwargs}")
                docs = app_state.vectorstore.similarity_search(query, **search_kwargs)
                logger.info(f"[Stream] Retrieved {len(docs)} documents")

                yield f"data: {json.dumps({'type': 'stage', 'stage': 'analyzing', 'message': '관련 구절 분석 중...'})}\n\n"
                await asyncio.sleep(0.1)

                context = "\n\n---\n\n".join([doc.page_content for doc in docs])
                sources = []
                seen_sutras = set()
                try:
                    cache_data = await sutra_cache.get_data()
                    summaries = cache_data.get("summaries", {})
                except Exception:
                    summaries = {}

                for doc in docs:
                    meta = doc.metadata
                    sutra_id = meta.get("sutra_id", meta.get("text_id", "unknown"))
                    if sutra_id in seen_sutras:
                        continue
                    seen_sutras.add(sutra_id)
                    cached_info = summaries.get(sutra_id, {})
                    title = cached_info.get("title_ko") or meta.get("title_ko") or meta.get("title", sutra_id)
                    sources.append(
                        {
                            "text_id": sutra_id,
                            "title": title,
                            "chunk_index": meta.get("chunk_index", 0),
                            "relevance_score": meta.get("relevance_score", 0.0),
                        }
                    )

                yield f"data: {json.dumps({'type': 'stage', 'stage': 'generating', 'message': '답변 작성 중...'})}\n\n"
                await asyncio.sleep(0.1)

                prompt_id = STREAMING_DETAILED_PROMPT_ID if is_detailed else STREAMING_NORMAL_PROMPT_ID
                retrieval_trace = RetrievalConfigTrace(
                    mode=(
                        "stream_sutra_filter"
                        if request.sutra_filter
                        else "stream_tradition_filter"
                        if tradition_sutra_ids and len(tradition_sutra_ids) > 0
                        else "stream_detailed"
                        if is_detailed
                        else "stream_default"
                    ),
                    top_k=retrieval_k,
                    max_sources=request.max_sources,
                    detailed_mode=is_detailed,
                    collection=request.collection,
                    filter_type=(
                        "sutra_id"
                        if request.sutra_filter
                        else "tradition"
                        if tradition_sutra_ids and len(tradition_sutra_ids) > 0
                        else None
                    ),
                    filter_value=request.sutra_filter if request.sutra_filter else tradition_filter_normalized,
                    filter_sutra_count=(
                        len(tradition_sutra_ids) if tradition_sutra_ids and len(tradition_sutra_ids) > 0 else None
                    ),
                    hyde_applied=bool(app_state.hyde_expander and not is_detailed),
                )
                prompt = build_prompt(prompt_id).format(context=context, question=request.query)
                query_trace = build_query_trace(
                    prompt_id=prompt_id,
                    retrieval=retrieval_trace,
                    response_mode="detailed" if is_detailed else "normal",
                    streaming=True,
                    model=model_name,
                    provider=get_provider_for_model_fn(model_name, gemini_provider=config.gemini_provider),
                )

                full_response = ""
                async for chunk in llm.astream(prompt):
                    if hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        full_response += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                latency_ms = int((time.time() - start_time) * 1000)

                log_token_usage(
                    query=request.query,
                    response=full_response[:500],
                    input_tokens=0,
                    output_tokens=0,
                    model=model_name,
                    mode="stream_detailed" if is_detailed else "stream_normal",
                    session_id=session_uuid,
                    latency_ms=latency_ms,
                    from_cache=False,
                    trace=query_trace,
                )

                async def save_to_db_and_usage():
                    try:
                        async with database.SessionLocal() as db_session:
                            await save_chat_to_db(
                                db=db_session,
                                session_uuid=session_uuid,
                                user_id=user_id,
                                user_message=request.query,
                                assistant_message=full_response,
                                metadata={
                                    "model": model_name,
                                    "sources_count": len(sources),
                                    "sources": sources,
                                    "response_mode": "detailed" if is_detailed else "normal",
                                    "latency_ms": latency_ms,
                                    "query_trace": query_trace,
                                },
                            )
                            if user_id:
                                stmt = select(User).where(User.id == user_id)
                                result = await db_session.execute(stmt)
                                user_for_usage = result.scalar_one_or_none()
                            else:
                                user_for_usage = None
                            await increment_usage(db_session, http_request, user_for_usage, tokens=0)
                    except Exception as exc:
                        logger.error(f"[Stream] DB save/usage error: {exc}")

                asyncio.create_task(save_to_db_and_usage())
                update_session_fn(
                    session_id=session_uuid,
                    user_message=request.query,
                    assistant_message=full_response,
                    context_chunks=docs,
                    metadata={
                        "model": model_name,
                        "response_mode": "detailed" if is_detailed else "normal",
                        "latency_ms": latency_ms,
                        "sources": sources,
                        "query_trace": query_trace,
                    },
                )
                yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency_ms, 'model': model_name, 'session_id': session_uuid})}\n\n"
                logger.info(f"[Stream] Completed in {latency_ms}ms, model={model_name}, user_id={user_id}")
            except Exception as exc:
                logger.error(f"[Stream] Error: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
