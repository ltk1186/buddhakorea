"""
HyDE (Hypothetical Document Embeddings) Query Expansion

This module implements HyDE for improving retrieval quality by:
1. Generating a hypothetical document that would answer the query
2. Embedding both the original query and hypothetical document
3. Searching with the combined embedding

Reference: Gemini Deep Research Report Section II.C
"""

from openai import OpenAI
from typing import Optional
import os

class HyDEQueryExpander:
    """
    Expands user queries using HyDE (Hypothetical Document Embeddings).
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize HyDE with OpenAI.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use for generation
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_hypothetical_document(self, query: str) -> Optional[str]:
        """
        Generate a hypothetical document that would answer the query.

        Args:
            query: User's original question

        Returns:
            Hypothetical document text, or None if generation fails
        """
        prompt = f"""당신은 CBETA 대장경 전문가입니다. 다음 질문에 대한 간결하고 정확한 답변을 작성하세요.
질문을 직접 답변하지 말고, 대장경에서 이 질문의 답이 될 만한 구절을 생성하세요.

질문: {query}

대장경 구절 (100-150자):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )

            hypothetical_doc = response.choices[0].message.content.strip()
            return hypothetical_doc if hypothetical_doc else None

        except Exception as e:
            print(f"HyDE generation error: {e}")
            return None

    def expand_query(self, query: str, weight_original: float = 0.5) -> str:
        """
        Expand query using HyDE.

        Args:
            query: Original user query
            weight_original: Weight for original query (0.0 to 1.0)
                           0.0 = use only hypothetical document
                           1.0 = use only original query
                           0.5 = balanced (recommended)

        Returns:
            Expanded query text combining original and hypothetical
        """
        hyp_doc = self.generate_hypothetical_document(query)

        if not hyp_doc:
            # Fallback to original query if HyDE fails
            return query

        # Combine original query and hypothetical document
        if weight_original == 1.0:
            return query
        elif weight_original == 0.0:
            return hyp_doc
        else:
            # Weighted combination (simply concatenate for embedding)
            return f"{query}\n\n{hyp_doc}"
