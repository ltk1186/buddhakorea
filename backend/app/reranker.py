"""
Reranker Module for Buddhist Text Retrieval

Provides cross-encoder reranking on top of bi-encoder retrieval.

Architecture:
1. Bi-encoder (bert-ancient-chinese-finetuned): Fast retrieval of top-K candidates
2. Cross-encoder (ms-marco-MiniLM-L-12-v2): Precise reranking to top-N

Reference: Gemini Deep Research Report Section II.B.3
"""

from sentence_transformers import CrossEncoder
from typing import List, Dict, Tuple
import time
import logging

logger = logging.getLogger(__name__)

class Reranker:
    """
    Cross-encoder reranker for improving retrieval precision.

    Usage:
        reranker = Reranker()
        reranked = reranker.rerank(query, candidates, top_n=10)
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
        batch_size: int = 32
    ):
        """
        Initialize reranker.

        Args:
            model_name: HuggingFace cross-encoder model name
            batch_size: Batch size for scoring (larger = faster but more memory)
        """
        self.model_name = model_name
        self.batch_size = batch_size

        logger.info(f"Loading reranker model: {model_name}")
        start_time = time.time()

        self.model = CrossEncoder(model_name)

        load_time = time.time() - start_time
        logger.info(f"Reranker loaded in {load_time:.2f}s")

    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_n: int = 10,
        return_scores: bool = True
    ) -> List[Dict]:
        """
        Rerank candidates using cross-encoder.

        Args:
            query: User query text
            candidates: List of candidate documents from bi-encoder retrieval
                       Each dict should have at least a 'text' or 'document' key
            top_n: Number of top results to return after reranking
            return_scores: If True, add 'rerank_score' to each result

        Returns:
            Reranked list of top-N candidates with scores
        """
        if not candidates:
            return []

        start_time = time.time()

        # Extract text from candidates
        # Support both 'document' (current) and 'text' keys
        texts = []
        for cand in candidates:
            if 'document' in cand:
                texts.append(cand['document'])
            elif 'text' in cand:
                texts.append(cand['text'])
            elif 'content' in cand:
                texts.append(cand['content'])
            else:
                logger.warning(f"Candidate missing text field: {cand.keys()}")
                texts.append("")

        # Create query-document pairs
        pairs = [(query, text) for text in texts]

        # Score all pairs
        scores = self.model.predict(pairs, batch_size=self.batch_size)

        # Add scores to candidates
        for i, cand in enumerate(candidates):
            if return_scores:
                cand['rerank_score'] = float(scores[i])

        # Sort by rerank score (descending)
        reranked = sorted(candidates, key=lambda x: x.get('rerank_score', 0), reverse=True)

        # Return top-N
        results = reranked[:top_n]

        elapsed = time.time() - start_time
        logger.info(
            f"Reranked {len(candidates)} candidates to top-{top_n} in {elapsed*1000:.1f}ms"
        )

        return results

    def batch_rerank(
        self,
        queries: List[str],
        candidates_list: List[List[Dict]],
        top_n: int = 10
    ) -> List[List[Dict]]:
        """
        Rerank multiple queries in batch.

        Args:
            queries: List of query texts
            candidates_list: List of candidate lists (one per query)
            top_n: Number of top results per query

        Returns:
            List of reranked results (one list per query)
        """
        results = []
        for query, candidates in zip(queries, candidates_list):
            reranked = self.rerank(query, candidates, top_n=top_n)
            results.append(reranked)
        return results

# Singleton instance (lazy loading)
_reranker_instance = None

def get_reranker() -> Reranker:
    """
    Get singleton reranker instance.

    Lazy loads the model on first call to avoid startup overhead.
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance

def rerank_results(
    query: str,
    results: List[Dict],
    top_n: int = 10,
    enabled: bool = True
) -> List[Dict]:
    """
    Convenience function for reranking results.

    Args:
        query: User query
        results: Candidate results from retrieval
        top_n: Number of top results to return
        enabled: If False, just return results[:top_n] without reranking

    Returns:
        Reranked top-N results
    """
    if not enabled or not results:
        return results[:top_n]

    reranker = get_reranker()
    return reranker.rerank(query, results, top_n=top_n)
