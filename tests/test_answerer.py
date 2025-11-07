"""Test suite for Answerer module.

This module tests LLM-based answer generation using retrieved context
for the Buddhist RAG system.

Following TDD: These tests are written BEFORE implementation.
"""

from typing import List
from unittest.mock import Mock

import pytest

from src.answerer import (
    Answerer,
    AnswererConfig,
    OpenAIAdapter,
    ClaudeAdapter,
    LLMAdapter,
    AnswerResponse,
    AnsweringError,
)
from src.retriever import RetrievalResult


class TestAnswererConfig:
    """Test AnswererConfig data class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = AnswererConfig()

        assert config.llm_backend == "openai"
        assert config.openai_model == "gpt-4-turbo-preview"
        assert config.temperature == 0.7
        assert config.max_tokens == 1000

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = AnswererConfig(
            llm_backend="claude",
            claude_model="claude-3-5-sonnet-20241022",
            temperature=0.5,
            max_tokens=2000,
            include_sources=True,
        )

        assert config.llm_backend == "claude"
        assert config.claude_model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000
        assert config.include_sources is True


class TestAnswerResponse:
    """Test AnswerResponse data class."""

    def test_response_creation(self) -> None:
        """Test creating answer response."""
        sources = [
            RetrievalResult(
                text="Source text",
                metadata={"sutra_id": "T0001"},
                score=0.95,
                rank=1,
            )
        ]

        response = AnswerResponse(
            answer="This is the answer text.",
            sources=sources,
            tokens_used=150,
        )

        assert response.answer == "This is the answer text."
        assert len(response.sources) == 1
        assert response.tokens_used == 150


class TestOpenAIAdapter:
    """Test OpenAI LLM adapter."""

    @pytest.mark.unit
    def test_adapter_initialization(self) -> None:
        """Test OpenAI adapter initializes correctly."""
        adapter = OpenAIAdapter(
            api_key="test-key",
            model="gpt-4-turbo-preview",
        )

        assert adapter.model == "gpt-4-turbo-preview"

    @pytest.mark.unit
    def test_generate_answer(self, mocker: Mock) -> None:
        """Test generating answer with mocked OpenAI."""
        # Mock OpenAI response
        mock_message = mocker.Mock()
        mock_message.content = "This is the Four Noble Truths answer."

        mock_choice = mocker.Mock()
        mock_choice.message = mock_message

        mock_response = mocker.Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mocker.Mock(total_tokens=200)

        mock_client = mocker.Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with mocker.patch("src.answerer.OpenAI", return_value=mock_client):
            adapter = OpenAIAdapter(api_key="test-key")
            answer = adapter.generate(
                prompt="Test prompt",
                temperature=0.7,
                max_tokens=1000,
            )

        assert answer == "This is the Four Noble Truths answer."

    @pytest.mark.unit
    def test_generate_handles_error(self, mocker: Mock) -> None:
        """Test adapter handles OpenAI API errors."""
        mock_client = mocker.Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with mocker.patch("src.answerer.OpenAI", return_value=mock_client):
            adapter = OpenAIAdapter(api_key="test-key")

            with pytest.raises(AnsweringError) as exc_info:
                adapter.generate("test prompt")

            assert "API Error" in str(exc_info.value)


class TestClaudeAdapter:
    """Test Claude (Anthropic) LLM adapter."""

    @pytest.mark.unit
    def test_adapter_initialization(self) -> None:
        """Test Claude adapter initializes correctly."""
        adapter = ClaudeAdapter(
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        assert adapter.model == "claude-3-5-sonnet-20241022"

    @pytest.mark.unit
    def test_generate_answer(self, mocker: Mock) -> None:
        """Test generating answer with mocked Claude."""
        # Mock Claude response
        mock_content = mocker.Mock()
        mock_content.text = "This is Claude's answer about Buddhist teachings."

        mock_response = mocker.Mock()
        mock_response.content = [mock_content]
        mock_response.usage = mocker.Mock(
            input_tokens=100,
            output_tokens=80,
        )

        mock_client = mocker.Mock()
        mock_client.messages.create.return_value = mock_response

        with mocker.patch("src.answerer.Anthropic", return_value=mock_client):
            adapter = ClaudeAdapter(api_key="test-key")
            answer = adapter.generate(
                prompt="Test prompt",
                temperature=0.7,
                max_tokens=1000,
            )

        assert answer == "This is Claude's answer about Buddhist teachings."

    @pytest.mark.unit
    def test_generate_handles_error(self, mocker: Mock) -> None:
        """Test adapter handles Claude API errors."""
        mock_client = mocker.Mock()
        mock_client.messages.create.side_effect = Exception("API Error")

        with mocker.patch("src.answerer.Anthropic", return_value=mock_client):
            adapter = ClaudeAdapter(api_key="test-key")

            with pytest.raises(AnsweringError):
                adapter.generate("test prompt")


class TestAnswerer:
    """Test Answerer class."""

    @pytest.mark.unit
    def test_answerer_initialization(self, mocker: Mock) -> None:
        """Test answerer initializes with LLM adapter."""
        mock_adapter = mocker.Mock(spec=LLMAdapter)
        config = AnswererConfig()

        answerer = Answerer(llm_adapter=mock_adapter, config=config)

        assert answerer.llm_adapter == mock_adapter
        assert answerer.config == config

    @pytest.mark.unit
    def test_assemble_context_from_results(self) -> None:
        """Test assembling context string from retrieval results."""
        results = [
            RetrievalResult(
                text="First teaching about suffering.",
                metadata={"sutra_id": "T0001", "chapter": "1"},
                score=0.95,
                rank=1,
            ),
            RetrievalResult(
                text="Second teaching about the path.",
                metadata={"sutra_id": "T0002", "chapter": "3"},
                score=0.85,
                rank=2,
            ),
        ]

        mock_adapter = Mock()
        answerer = Answerer(llm_adapter=mock_adapter)

        context = answerer._assemble_context(results)

        assert "First teaching about suffering" in context
        assert "Second teaching about the path" in context
        assert "T0001" in context
        assert "T0002" in context

    @pytest.mark.unit
    def test_build_prompt(self) -> None:
        """Test building prompt with query and context."""
        results = [
            RetrievalResult(
                text="Teaching text",
                metadata={"sutra_id": "T0001"},
                score=0.9,
                rank=1,
            )
        ]

        mock_adapter = Mock()
        answerer = Answerer(llm_adapter=mock_adapter)

        prompt = answerer._build_prompt(
            query="What is the teaching?",
            context="Teaching text",
        )

        assert "What is the teaching?" in prompt
        assert "Teaching text" in prompt
        # Should include instructions
        assert len(prompt) > 50

    @pytest.mark.unit
    def test_answer_with_context(self, mocker: Mock) -> None:
        """Test generating answer from query and context."""
        results = [
            RetrievalResult(
                text="The Four Noble Truths are...",
                metadata={"sutra_id": "T0001"},
                score=0.95,
                rank=1,
            )
        ]

        mock_adapter = mocker.Mock()
        mock_adapter.generate.return_value = "The Four Noble Truths explain..."
        mock_adapter.get_token_usage.return_value = 250

        config = AnswererConfig()
        answerer = Answerer(llm_adapter=mock_adapter, config=config)

        response = answerer.answer(
            query="What are the Four Noble Truths?",
            context_results=results,
        )

        assert isinstance(response, AnswerResponse)
        assert "Four Noble Truths" in response.answer
        assert len(response.sources) == 1
        assert response.tokens_used == 250

    @pytest.mark.unit
    def test_answer_without_context(self, mocker: Mock) -> None:
        """Test answering with empty context."""
        mock_adapter = mocker.Mock()
        mock_adapter.generate.return_value = "I don't have enough context."
        mock_adapter.get_token_usage.return_value = 50

        answerer = Answerer(llm_adapter=mock_adapter)

        response = answerer.answer(
            query="What is this?",
            context_results=[],
        )

        assert "context" in response.answer.lower()
        assert len(response.sources) == 0

    @pytest.mark.unit
    def test_answer_handles_llm_error(self, mocker: Mock) -> None:
        """Test answerer handles LLM generation errors."""
        results = [
            RetrievalResult(
                text="Test",
                metadata={},
                score=0.9,
                rank=1,
            )
        ]

        mock_adapter = mocker.Mock()
        mock_adapter.generate.side_effect = Exception("LLM failed")

        answerer = Answerer(llm_adapter=mock_adapter)

        with pytest.raises(AnsweringError):
            answerer.answer("test query", results)

    @pytest.mark.unit
    def test_answer_includes_sources_when_enabled(self, mocker: Mock) -> None:
        """Test that sources are included in response when configured."""
        results = [
            RetrievalResult(
                text="Source 1",
                metadata={"sutra_id": "T0001"},
                score=0.9,
                rank=1,
            ),
            RetrievalResult(
                text="Source 2",
                metadata={"sutra_id": "T0002"},
                score=0.8,
                rank=2,
            ),
        ]

        mock_adapter = mocker.Mock()
        mock_adapter.generate.return_value = "Answer"
        mock_adapter.get_token_usage.return_value = 100

        config = AnswererConfig(include_sources=True)
        answerer = Answerer(llm_adapter=mock_adapter, config=config)

        response = answerer.answer("test", results)

        assert len(response.sources) == 2
        assert response.sources[0].metadata["sutra_id"] == "T0001"

    @pytest.mark.unit
    def test_answer_respects_temperature_config(self, mocker: Mock) -> None:
        """Test that temperature config is passed to LLM."""
        mock_adapter = mocker.Mock()
        mock_adapter.generate.return_value = "Answer"
        mock_adapter.get_token_usage.return_value = 100

        config = AnswererConfig(temperature=0.3, max_tokens=500)
        answerer = Answerer(llm_adapter=mock_adapter, config=config)

        answerer.answer("test", [])

        # Verify adapter was called with correct parameters
        call_kwargs = mock_adapter.generate.call_args[1]
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 500

    @pytest.mark.unit
    def test_answer_with_korean_query(self, mocker: Mock) -> None:
        """Test answering Korean language query."""
        results = [
            RetrievalResult(
                text="사성제에 대한 설명",
                metadata={"sutra_id": "T0001"},
                score=0.95,
                rank=1,
            )
        ]

        mock_adapter = mocker.Mock()
        mock_adapter.generate.return_value = "사성제는 불교의 핵심 가르침입니다."
        mock_adapter.get_token_usage.return_value = 180

        answerer = Answerer(llm_adapter=mock_adapter)

        response = answerer.answer("사성제란 무엇입니까?", results)

        assert "사성제" in response.answer
        # Verify Korean text was passed to LLM
        call_kwargs = mock_adapter.generate.call_args[1]
        assert "사성제란 무엇입니까?" in call_kwargs["prompt"]


class TestAnswererFactory:
    """Test Answerer factory methods."""

    @pytest.mark.unit
    def test_from_config_creates_openai_adapter(self, mocker: Mock) -> None:
        """Test creating answerer with OpenAI from config."""
        config = AnswererConfig(
            llm_backend="openai",
            openai_api_key="test-key",
        )

        mock_adapter_class = mocker.patch("src.answerer.OpenAIAdapter")
        answerer = Answerer.from_config(config)

        mock_adapter_class.assert_called_once()

    @pytest.mark.unit
    def test_from_config_creates_claude_adapter(self, mocker: Mock) -> None:
        """Test creating answerer with Claude from config."""
        config = AnswererConfig(
            llm_backend="claude",
            claude_api_key="test-key",
        )

        mock_adapter_class = mocker.patch("src.answerer.ClaudeAdapter")
        answerer = Answerer.from_config(config)

        mock_adapter_class.assert_called_once()

    @pytest.mark.unit
    def test_from_config_raises_on_invalid_backend(self) -> None:
        """Test that invalid backend raises error."""
        config = AnswererConfig(llm_backend="invalid")

        with pytest.raises(ValueError) as exc_info:
            Answerer.from_config(config)

        assert "Invalid backend" in str(exc_info.value)


class TestIntegrationAnswerer:
    """Integration tests for complete answering workflow."""

    @pytest.mark.integration
    def test_end_to_end_answering_with_openai(self, mocker: Mock) -> None:
        """Test complete answering workflow with mocked OpenAI."""
        # Mock OpenAI
        mock_message = mocker.Mock()
        mock_message.content = "The Four Noble Truths are the foundation of Buddhism."

        mock_choice = mocker.Mock()
        mock_choice.message = mock_message

        mock_response = mocker.Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mocker.Mock(total_tokens=300)

        mock_client = mocker.Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with mocker.patch("src.answerer.OpenAI", return_value=mock_client):
            config = AnswererConfig(
                llm_backend="openai",
                openai_api_key="test",
            )
            answerer = Answerer.from_config(config)

            # Create context
            results = [
                RetrievalResult(
                    text="The Four Noble Truths: suffering, cause, cessation, path.",
                    metadata={"sutra_id": "T0001"},
                    score=0.95,
                    rank=1,
                )
            ]

            # Generate answer
            response = answerer.answer(
                query="What are the Four Noble Truths?",
                context_results=results,
            )

            assert "Four Noble Truths" in response.answer
            assert response.tokens_used > 0
            assert len(response.sources) == 1

    @pytest.mark.integration
    def test_end_to_end_answering_with_claude(self, mocker: Mock) -> None:
        """Test complete answering workflow with mocked Claude."""
        # Mock Claude
        mock_content = mocker.Mock()
        mock_content.text = "Buddhism teaches the Noble Eightfold Path."

        mock_response = mocker.Mock()
        mock_response.content = [mock_content]
        mock_response.usage = mocker.Mock(input_tokens=150, output_tokens=100)

        mock_client = mocker.Mock()
        mock_client.messages.create.return_value = mock_response

        with mocker.patch("src.answerer.Anthropic", return_value=mock_client):
            config = AnswererConfig(
                llm_backend="claude",
                claude_api_key="test",
            )
            answerer = Answerer.from_config(config)

            results = [
                RetrievalResult(
                    text="The Eightfold Path consists of...",
                    metadata={"sutra_id": "T0002"},
                    score=0.9,
                    rank=1,
                )
            ]

            response = answerer.answer(
                query="What is the Eightfold Path?",
                context_results=results,
            )

            assert "Eightfold Path" in response.answer
            assert response.tokens_used == 250  # 150 + 100
