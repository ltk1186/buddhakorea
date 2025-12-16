"""Answerer module for LLM-based answer generation.

This module uses LLMs (OpenAI or Claude) to generate answers from retrieved
context for the Buddhist RAG system.

Example:
    ```python
    # Setup
    config = AnswererConfig(
        llm_backend="openai",
        openai_api_key="...",
        temperature=0.7
    )
    answerer = Answerer.from_config(config)

    # Generate answer
    response = answerer.answer(
        query="What are the Four Noble Truths?",
        context_results=retrieval_results
    )

    print(response.answer)
    print(f"Used {response.tokens_used} tokens")
    ```
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from anthropic import Anthropic
from openai import OpenAI

from src.retriever import RetrievalResult


class AnsweringError(Exception):
    """Raised when answer generation fails."""

    pass


@dataclass
class AnswererConfig:
    """Configuration for answerer.

    Attributes:
        llm_backend: "openai" or "claude"
        openai_api_key: OpenAI API key
        openai_model: OpenAI model name
        claude_api_key: Claude API key
        claude_model: Claude model name
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens in response
        include_sources: Whether to include sources in response
    """

    llm_backend: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    claude_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 1000
    include_sources: bool = True


@dataclass
class AnswerResponse:
    """Response from answer generation.

    Attributes:
        answer: The generated answer text
        sources: List of source RetrievalResults used
        tokens_used: Number of tokens consumed
    """

    answer: str
    sources: List[RetrievalResult] = field(default_factory=list)
    tokens_used: int = 0


class LLMAdapter(Protocol):
    """Protocol for LLM adapters."""

    def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000
    ) -> str:
        """Generate text from prompt."""
        ...

    def get_token_usage(self) -> int:
        """Get token usage from last generation."""
        ...


class OpenAIAdapter:
    """OpenAI LLM adapter."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key
            model: Model name
        """
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key)
        self._last_token_usage = 0

    def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000
    ) -> str:
        """Generate answer using OpenAI.

        Args:
            prompt: System prompt with context and query
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Generated answer text

        Raises:
            AnsweringError: If generation fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Store token usage
            self._last_token_usage = response.usage.total_tokens

            return response.choices[0].message.content

        except Exception as e:
            raise AnsweringError(f"OpenAI generation failed: {e}") from e

    def get_token_usage(self) -> int:
        """Get token usage from last generation."""
        return self._last_token_usage


class ClaudeAdapter:
    """Claude (Anthropic) LLM adapter."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize Claude adapter.

        Args:
            api_key: Anthropic API key
            model: Model name
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key)
        self._last_token_usage = 0

    def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000
    ) -> str:
        """Generate answer using Claude.

        Args:
            prompt: User prompt with context and query
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Generated answer text

        Raises:
            AnsweringError: If generation fails
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Store token usage (input + output)
            self._last_token_usage = (
                response.usage.input_tokens + response.usage.output_tokens
            )

            return response.content[0].text

        except Exception as e:
            raise AnsweringError(f"Claude generation failed: {e}") from e

    def get_token_usage(self) -> int:
        """Get token usage from last generation."""
        return self._last_token_usage


class Answerer:
    """LLM-based answerer for RAG system.

    Example:
        ```python
        answerer = Answerer.from_config(config)
        response = answerer.answer(query, context_results)
        ```
    """

    def __init__(
        self,
        llm_adapter: Optional[LLMAdapter] = None,
        config: Optional[AnswererConfig] = None,
    ):
        """Initialize answerer.

        Args:
            llm_adapter: LLM adapter instance
            config: Answerer configuration
        """
        self.llm_adapter = llm_adapter
        self.config = config if config is not None else AnswererConfig()

    @classmethod
    def from_config(cls, config: AnswererConfig) -> "Answerer":
        """Create answerer from configuration.

        Args:
            config: Answerer configuration

        Returns:
            Configured Answerer instance

        Raises:
            ValueError: If backend is invalid or API key is missing
        """
        if config.llm_backend == "openai":
            if not config.openai_api_key:
                raise ValueError("openai_api_key required for OpenAI backend")

            adapter = OpenAIAdapter(
                api_key=config.openai_api_key,
                model=config.openai_model,
            )
        elif config.llm_backend == "claude":
            if not config.claude_api_key:
                raise ValueError("claude_api_key required for Claude backend")

            adapter = ClaudeAdapter(
                api_key=config.claude_api_key,
                model=config.claude_model,
            )
        else:
            raise ValueError(f"Invalid backend: {config.llm_backend}")

        return cls(llm_adapter=adapter, config=config)

    def answer(
        self,
        query: str,
        context_results: List[RetrievalResult],
    ) -> AnswerResponse:
        """Generate answer from query and retrieved context.

        Args:
            query: User's question
            context_results: Retrieved context chunks

        Returns:
            AnswerResponse with generated answer and metadata

        Raises:
            AnsweringError: If answer generation fails
        """
        try:
            # Assemble context from results
            context = self._assemble_context(context_results)

            # Build prompt
            prompt = self._build_prompt(query, context)

            # Generate answer
            answer = self.llm_adapter.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            # Get token usage
            tokens_used = self.llm_adapter.get_token_usage()

            # Build response
            sources = context_results if self.config.include_sources else []

            return AnswerResponse(
                answer=answer,
                sources=sources,
                tokens_used=tokens_used,
            )

        except Exception as e:
            raise AnsweringError(f"Answer generation failed: {e}") from e

    def _assemble_context(self, results: List[RetrievalResult]) -> str:
        """Assemble context string from retrieval results.

        Args:
            results: List of retrieval results

        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant context found."

        context_parts = []
        for result in results:
            # Format: [Source: sutra_id, chapter] text
            source_info = result.metadata.get("sutra_id", "Unknown")
            if "chapter" in result.metadata:
                source_info += f", Chapter {result.metadata['chapter']}"

            context_parts.append(f"[Source: {source_info}]\n{result.text}")

        return "\n\n".join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build prompt for LLM.

        Args:
            query: User's question
            context: Assembled context

        Returns:
            Complete prompt string
        """
        prompt = f"""You are a knowledgeable Buddhist scholar assistant. Your task is to answer questions about Buddhist teachings based on the provided context from Buddhist sutras.

Context from Buddhist texts:
{context}

User's question: {query}

Instructions:
1. Answer the question based ONLY on the provided context
2. If the context doesn't contain enough information, say so clearly
3. Be accurate and respectful of Buddhist teachings
4. Cite the source (sutra ID) when referencing specific teachings
5. Keep your answer clear and concise

Answer:"""

        return prompt
