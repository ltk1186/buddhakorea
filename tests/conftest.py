"""Shared pytest fixtures for Buddhist RAG System tests."""

import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@pytest.fixture
def sample_tei_xml() -> str:
    """Sample TEI P5 XML document for testing chunker.

    Returns:
        XML string representing a simple Buddhist sutra
    """
    return """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc>
            <titleStmt>
                <title>Test Sutra</title>
            </titleStmt>
            <sourceDesc>
                <bibl>T0001</bibl>
            </sourceDesc>
        </fileDesc>
    </teiHeader>
    <text>
        <body>
            <div type="chapter" n="1">
                <head>Chapter 1</head>
                <p>This is the first paragraph of Buddhist teaching about impermanence.</p>
                <p>This is the second paragraph about suffering and the path to liberation.</p>
            </div>
            <div type="chapter" n="2">
                <head>Chapter 2</head>
                <p>This chapter discusses the Noble Eightfold Path in detail.</p>
            </div>
        </body>
    </text>
</TEI>
"""


@pytest.fixture
def sample_chunks() -> List[Dict[str, Any]]:
    """Sample text chunks with metadata.

    Returns:
        List of chunk dictionaries
    """
    return [
        {
            "text": "This is the first paragraph of Buddhist teaching about impermanence.",
            "metadata": {
                "sutra_id": "T0001",
                "chapter": "1",
                "paragraph": "1",
                "char_count": 69,
            },
        },
        {
            "text": "This is the second paragraph about suffering and the path to liberation.",
            "metadata": {
                "sutra_id": "T0001",
                "chapter": "1",
                "paragraph": "2",
                "char_count": 73,
            },
        },
        {
            "text": "This chapter discusses the Noble Eightfold Path in detail.",
            "metadata": {
                "sutra_id": "T0001",
                "chapter": "2",
                "paragraph": "1",
                "char_count": 59,
            },
        },
    ]


@pytest.fixture
def sample_embeddings() -> np.ndarray:
    """Sample embeddings for testing.

    Returns:
        NumPy array of shape (3, 384) representing 3 embeddings
    """
    np.random.seed(42)  # For reproducibility
    return np.random.rand(3, 384).astype(np.float32)


@pytest.fixture
def mock_openai_response(mocker: Any) -> Any:
    """Mock OpenAI API response for embeddings.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mocked response object
    """
    mock_embedding_1 = mocker.Mock()
    mock_embedding_1.embedding = np.random.rand(1536).tolist()

    mock_embedding_2 = mocker.Mock()
    mock_embedding_2.embedding = np.random.rand(1536).tolist()

    mock_response = mocker.Mock()
    mock_response.data = [mock_embedding_1, mock_embedding_2]

    return mock_response


@pytest.fixture
def mock_claude_response(mocker: Any) -> Any:
    """Mock Anthropic Claude API response.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mocked response object
    """
    mock_response = mocker.Mock()
    mock_response.content = [
        mocker.Mock(text="This is a test response from Claude about Buddhist teachings.")
    ]
    mock_response.usage = mocker.Mock(input_tokens=100, output_tokens=50)

    return mock_response


@pytest.fixture
def temp_chroma_dir(tmp_path: Path) -> Path:
    """Temporary directory for ChromaDB testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to temporary ChromaDB directory
    """
    chroma_dir = tmp_path / "chroma_test"
    chroma_dir.mkdir(exist_ok=True)
    return chroma_dir


@pytest.fixture
def sample_query() -> str:
    """Sample query for testing retrieval and answering.

    Returns:
        Query string in Korean
    """
    return "사성제란 무엇입니까?"  # "What are the Four Noble Truths?"


@pytest.fixture
def sample_context() -> List[Dict[str, Any]]:
    """Sample retrieved context for testing answerer.

    Returns:
        List of retrieved chunk dictionaries with scores
    """
    return [
        {
            "text": "사성제는 고성제(苦聖諦), 집성제(集聖諦), 멸성제(滅聖諦), 도성제(道聖諦)로 구성됩니다.",
            "metadata": {"sutra_id": "T0001", "chapter": "1"},
            "score": 0.95,
        },
        {
            "text": "고성제는 삶의 괴로움을 인정하는 진리입니다.",
            "metadata": {"sutra_id": "T0001", "chapter": "1"},
            "score": 0.89,
        },
        {
            "text": "도성제는 팔정도를 통해 해탈에 이르는 길을 가르칩니다.",
            "metadata": {"sutra_id": "T0002", "chapter": "3"},
            "score": 0.85,
        },
    ]


@pytest.fixture(autouse=True)
def reset_env_vars() -> None:
    """Reset environment variables before each test."""
    # Store original values
    original_env = dict(os.environ)

    yield

    # Restore original values after test
    os.environ.clear()
    os.environ.update(original_env)
