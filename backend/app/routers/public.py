"""Public content, analytics, and static page routers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import database
from ..api_schemas import CachedResponseInfo, CacheRequest
from ..dependencies import get_current_user_optional
from ..models.user import User
from ..tradition_normalizer import get_normalized_traditions, normalize_tradition
from ..usage_tracker import analyze_usage_logs, export_usage_csv, get_recent_queries
from ..qa_logger import analyze_popular_queries, export_to_json, get_qa_pairs


def create_public_router(
    *,
    app_state: Any,
    logger: Any,
    frontend_dir: Path,
    sutra_cache: Any,
    response_cache: dict[str, dict[str, Any]],
    add_to_cache_fn: Any,
    remove_from_cache_fn: Any,
    get_usage_info_fn: Any,
) -> APIRouter:
    router = APIRouter(tags=["public"])

    def read_html(name: str) -> HTMLResponse:
        return HTMLResponse(content=(frontend_dir / name).read_text(encoding="utf-8"))

    @router.get("/api/qa-pairs")
    async def get_qa_pairs_endpoint(
        days: int = 7,
        limit: Optional[int] = None,
        detailed_mode_only: bool = False,
        sutra_filter_only: bool = False,
        sutra_filter: Optional[str] = None,
    ):
        try:
            pairs = get_qa_pairs(
                days=days,
                limit=limit,
                detailed_mode_only=detailed_mode_only,
                sutra_filter_only=sutra_filter_only,
                sutra_filter=sutra_filter,
            )
            return {"count": len(pairs), "days": days, "qa_pairs": pairs}
        except Exception as exc:
            logger.error(f"Error retrieving Q&A pairs: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving Q&A pairs: {str(exc)}",
            )

    @router.get("/api/qa-pairs/export")
    async def export_qa_pairs_endpoint(
        days: int = 30,
        detailed_mode_only: bool = False,
        sutra_filter_only: bool = False,
        format: str = "json",
    ):
        try:
            if format != "json":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only 'json' format is currently supported")

            output_file = "logs/qa_pairs_export.json"
            success = export_to_json(
                output_file=output_file,
                days=days,
                detailed_mode_only=detailed_mode_only,
                sutra_filter_only=sutra_filter_only,
            )
            if not success:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Export failed")

            return {
                "status": "success",
                "output_file": output_file,
                "days": days,
                "filters": {
                    "detailed_mode_only": detailed_mode_only,
                    "sutra_filter_only": sutra_filter_only,
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error exporting Q&A pairs: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error exporting Q&A pairs: {str(exc)}",
            )

    @router.get("/api/qa-pairs/analytics")
    async def get_qa_analytics(days: int = 7, top_n: int = 10):
        try:
            stats = analyze_popular_queries(days=days, top_n=top_n)
            return {"days": days, "statistics": stats}
        except Exception as exc:
            logger.error(f"Error analyzing Q&A pairs: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error analyzing Q&A pairs: {str(exc)}",
            )

    @router.get("/")
    async def home_page():
        return read_html("index.html")

    @router.get("/index.html")
    async def home_page_html():
        return read_html("index.html")

    @router.get("/chat")
    async def chat_page():
        return read_html("chat.html")

    @router.get("/chat.html")
    async def chat_page_html():
        return read_html("chat.html")

    @router.get("/sutra-writing")
    async def sutra_writing_page():
        return read_html("sutra-writing.html")

    @router.get("/sutra-writing.html")
    async def sutra_writing_page_html():
        return read_html("sutra-writing.html")

    @router.get("/methodology")
    async def methodology_page():
        return read_html("methodology.html")

    @router.get("/methodology.html")
    async def methodology_page_html():
        return read_html("methodology.html")

    @router.get("/meditation")
    async def meditation_page():
        return read_html("meditation.html")

    @router.get("/meditation.html")
    async def meditation_page_html():
        return read_html("meditation.html")

    @router.get("/mypage")
    async def mypage_page():
        return read_html("mypage.html")

    @router.get("/mypage.html")
    async def mypage_page_html():
        return read_html("mypage.html")

    @router.get("/teaching")
    async def teaching_page():
        return read_html("teaching.html")

    @router.get("/teaching.html")
    async def teaching_page_html():
        return read_html("teaching.html")

    @router.get("/api/sutras/meta")
    async def get_sutra_metadata():
        try:
            metadata = await sutra_cache.get_metadata()
            metadata["traditions_normalized"] = get_normalized_traditions()
            return metadata
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error getting sutra metadata: {exc}")
            raise HTTPException(500, str(exc))

    @router.get("/api/sources")
    async def list_sources(
        search: Optional[str] = None,
        tradition: Optional[str] = None,
        period: Optional[str] = None,
        theme: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        try:
            data = await sutra_cache.get_data()
            summaries = data.get("summaries", {})
            filtered = []
            for sutra_id, source in summaries.items():
                if search:
                    search_lower = search.lower()
                    title_ko = source.get("title_ko", "").lower()
                    original_title = source.get("original_title", "").lower()
                    brief = source.get("brief_summary", "").lower()
                    if not (search_lower in title_ko or search_lower in original_title or search_lower in brief):
                        continue

                if tradition:
                    raw_trad = source.get("tradition", "")
                    normalized_trad = normalize_tradition(raw_trad)
                    if tradition.lower() != raw_trad.lower() and tradition != normalized_trad:
                        continue

                if period and source.get("period", "").lower() != period.lower():
                    continue

                if theme:
                    key_themes = source.get("key_themes", [])
                    if isinstance(key_themes, str):
                        key_themes = [key_themes]
                    if theme not in key_themes:
                        continue

                raw_tradition = source.get("tradition", "")
                filtered.append(
                    {
                        "sutra_id": sutra_id,
                        "title_ko": source.get("title_ko", ""),
                        "original_title": source.get("original_title", ""),
                        "author": source.get("author", ""),
                        "brief_summary": source.get("brief_summary", ""),
                        "tradition": raw_tradition,
                        "tradition_normalized": normalize_tradition(raw_tradition),
                        "period": source.get("period", ""),
                        "volume": source.get("volume", ""),
                        "juan": source.get("juan", ""),
                        "key_themes": source.get("key_themes", []),
                    }
                )

            filtered.sort(key=lambda item: item["sutra_id"])
            limit = min(limit, 3000)
            paginated = filtered[offset : offset + limit]
            return {"total": len(filtered), "limit": limit, "offset": offset, "sources": paginated}
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error listing sources: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api/sources/{sutra_id}")
    async def get_source_detail(sutra_id: str):
        try:
            summaries_path = "../data/source_data/source_summaries_ko.json"
            if not os.path.exists(summaries_path):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Source summaries not yet generated.",
                )

            with open(summaries_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            summaries = data.get("summaries", {})
            base_sutra_id = sutra_id.split(":")[0] if ":" in sutra_id else sutra_id
            if base_sutra_id not in summaries:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source {sutra_id} not found",
                )

            source = summaries[base_sutra_id]
            raw_tradition = source.get("tradition", "")
            return {
                "sutra_id": sutra_id,
                "title_ko": source.get("title_ko", ""),
                "original_title": source.get("original_title", ""),
                "author": source.get("author", ""),
                "volume": source.get("volume", ""),
                "juan": source.get("juan", ""),
                "brief_summary": source.get("brief_summary", ""),
                "detailed_summary": source.get("detailed_summary", ""),
                "key_themes": source.get("key_themes", []),
                "period": source.get("period", ""),
                "tradition": raw_tradition,
                "tradition_normalized": normalize_tradition(raw_tradition),
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error getting source detail: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.post("/api/cache")
    async def add_cache(request: CacheRequest):
        try:
            sources_dict = [
                source.model_dump() if hasattr(source, "model_dump") else source
                for source in request.sources
            ]
            add_to_cache_fn(
                cache_key=request.cache_key,
                keywords=request.keywords,
                response=request.response,
                sources=sources_dict,
                model=request.model,
                metadata=request.metadata,
            )
            return {
                "status": "success",
                "message": f"Response cached with key '{request.cache_key}'",
                "keywords": request.keywords,
            }
        except Exception as exc:
            logger.error(f"Error adding to cache: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api/cache", response_model=list[CachedResponseInfo])
    async def list_cache():
        try:
            cached_list = []
            for cache_key, cache_data in response_cache.items():
                cached_list.append(
                    CachedResponseInfo(
                        cache_key=cache_key,
                        keywords=cache_data.get("keywords", []),
                        response_preview=cache_data.get("response", "")[:200],
                        model=cache_data.get("model", ""),
                        created_at=cache_data.get("created_at", ""),
                        hit_count=cache_data.get("hit_count", 0),
                        last_hit=cache_data.get("last_hit"),
                    )
                )
            return cached_list
        except Exception as exc:
            logger.error(f"Error listing cache: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api/cache/{cache_key}")
    async def get_cache(cache_key: str):
        try:
            if cache_key not in response_cache:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Cache key '{cache_key}' not found",
                )
            return response_cache[cache_key]
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error getting cache: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api/usage")
    async def get_user_quota(
        http_request: Request,
        db: AsyncSession = Depends(database.get_db),
        user: Optional[User] = Depends(get_current_user_optional),
    ):
        return await get_usage_info_fn(db, http_request, user)

    @router.get("/api/usage-stats")
    async def get_usage_stats(days: int = 7, format: str = "json"):
        try:
            days = min(max(1, days), 90)
            stats = analyze_usage_logs(days=days)
            if format == "csv":
                import tempfile

                csv_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv")
                csv_path = csv_file.name
                csv_file.close()
                success = export_usage_csv(output_file=csv_path, days=days)
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to export CSV",
                    )
                return FileResponse(csv_path, media_type="text/csv", filename=f"usage_stats_{days}days.csv")

            return {
                "period_days": days,
                "total_queries": stats["total_queries"],
                "cached_queries": stats.get("cached_queries", 0),
                "api_queries": stats["total_queries"] - stats.get("cached_queries", 0),
                "total_cost_usd": round(stats["total_cost"], 4),
                "tokens": {
                    "input": stats["input_tokens"],
                    "output": stats["output_tokens"],
                    "total": stats["total_tokens"],
                },
                "by_mode": {
                    mode: {
                        "queries": data["queries"],
                        "cost_usd": round(data["cost"], 4),
                        "tokens": data["tokens"],
                        "avg_cost_per_query": round(data["cost"] / data["queries"], 6) if data["queries"] > 0 else 0,
                    }
                    for mode, data in stats.get("by_mode", {}).items()
                },
                "by_model": {
                    model: {
                        "queries": data["queries"],
                        "cost_usd": round(data["cost"], 4),
                        "tokens": data["tokens"],
                    }
                    for model, data in stats.get("by_model", {}).items()
                },
                "by_day": {
                    day: {
                        "queries": data["queries"],
                        "cost_usd": round(data["cost"], 4),
                        "tokens": data["tokens"],
                    }
                    for day, data in sorted(stats.get("by_day", {}).items())
                },
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error getting usage stats: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api/recent-queries")
    async def get_recent_queries_endpoint(limit: int = 10):
        try:
            limit = min(max(1, limit), 100)
            queries = get_recent_queries(limit=limit)
            return {"count": len(queries), "queries": queries}
        except Exception as exc:
            logger.error(f"Error getting recent queries: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.delete("/api/cache/{cache_key}")
    async def delete_cache(cache_key: str):
        try:
            if remove_from_cache_fn(cache_key):
                return {"status": "success", "message": f"Cache key '{cache_key}' deleted"}
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache key '{cache_key}' not found",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Error deleting cache: {exc}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    @router.get("/api")
    async def api_info():
        return {
            "message": "Buddhist AI Chatbot API",
            "version": "0.1.0",
            "endpoints": {
                "health": "/api/health",
                "chat": "/api/chat (POST)",
                "collections": "/api/collections",
                "sources": "/api/sources (GET) - List Buddhist texts",
                "source_detail": "/api/sources/{sutra_id} (GET) - Get text details",
                "docs": "/docs",
                "test_ui": "/",
            },
        }

    return router
