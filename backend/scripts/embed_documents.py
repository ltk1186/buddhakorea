"""
Document Embedding Script for Buddhist AI Chatbot

Processes Buddhist texts (CBETA, Pali Canon) and generates embeddings for RAG.

Usage:
    python scripts/embed_documents.py --input data/processed/ --batch-size 32
    python scripts/embed_documents.py --input data/processed/ --collection chinese --language zh
    python scripts/embed_documents.py --reset  # Warning: deletes existing embeddings
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


# ============================================================================
# Configuration
# ============================================================================

class EmbeddingConfig:
    """Configuration for embedding generation."""

    def __init__(self):
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL",
            "BAAI/bge-m3"  # Default to bge-m3 for better Classical Chinese support
        )
        self.chroma_db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        # Use CHUNK_SIZE from .env (default 1024 tokens ~= 1500 characters for Chinese)
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1024"))  # tokens
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))  # tokens
        self.batch_size = int(os.getenv("BATCH_SIZE", "128"))  # M4 Pro optimized
        self.max_workers = int(os.getenv("MAX_WORKERS", "12"))  # M4 Pro: 16 cores, leave 4


config = EmbeddingConfig()


# ============================================================================
# Document Loading
# ============================================================================

def load_documents_from_directory(input_dir: Path, file_pattern: str = "*.txt") -> List[Dict[str, Any]]:
    """
    Load all documents from a directory.

    Expected structure:
        data/processed/
        ├── chinese/
        │   ├── T0001_agama_sutra.json
        │   └── T0262_lotus_sutra.json
        └── english/
            ├── MN001_root_of_all_things.json
            └── SN56.11_dhammacakkappavattana.json

    Each JSON file format:
    {
        "text_id": "T0001",
        "title": "Āgama Sutra",
        "language": "zh",
        "category": "sutta",
        "translator": "...",
        "text": "Full text content...",
        "metadata": { ... }
    }
    """

    documents = []
    input_path = Path(input_dir)

    if not input_path.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return documents

    # Find all JSON files recursively
    json_files = list(input_path.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {input_dir}")

    for json_file in tqdm(json_files, desc="Loading documents"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Validate required fields
                if "text" not in data or "text_id" not in data:
                    logger.warning(f"Skipping {json_file}: missing 'text' or 'text_id' field")
                    continue

                documents.append(data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {json_file}: {e}")
        except Exception as e:
            logger.error(f"Error loading {json_file}: {e}")

    logger.info(f"Successfully loaded {len(documents)} documents")
    return documents


# ============================================================================
# Text Chunking
# ============================================================================

def chunk_documents(documents: List[Dict[str, Any]], chunk_size: int = 1024, overlap: int = 200) -> List[Document]:
    """
    Split documents into chunks for embedding.

    Args:
        documents: List of document dictionaries
        chunk_size: Maximum chunk size in TOKENS (for Chinese: ~1.5 chars per token)
        overlap: Overlap between chunks in tokens

    Returns:
        List of LangChain Document objects
    """

    # Convert tokens to characters for Chinese text
    # Research shows: Classical Chinese ~1.5 characters per token
    # So 1024 tokens ≈ 1536 characters for Chinese
    char_chunk_size = int(chunk_size * 1.5)
    char_overlap = int(overlap * 1.5)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=char_chunk_size,
        chunk_overlap=char_overlap,
        length_function=len,
        # Prioritize Chinese-specific separators for Classical Chinese texts
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""]
    )

    chunked_docs = []

    for doc_data in tqdm(documents, desc="Chunking documents"):
        text = doc_data.get("text", "")
        text_id = doc_data.get("text_id", "unknown")
        title = doc_data.get("title", "Untitled")
        language = doc_data.get("language", "unknown")
        category = doc_data.get("category", "general")

        # Split text into chunks
        chunks = text_splitter.split_text(text)

        # Create Document objects with metadata
        for i, chunk in enumerate(chunks):
            metadata = {
                "text_id": text_id,
                "title": title,
                "language": language,
                "category": category,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": doc_data.get("source", "unknown"),
                "translator": doc_data.get("translator", ""),
            }

            # Add any additional metadata from the document
            if "metadata" in doc_data:
                metadata.update(doc_data["metadata"])

            chunked_docs.append(Document(
                page_content=chunk,
                metadata=metadata
            ))

    logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} documents")
    return chunked_docs


# ============================================================================
# Embedding Generation
# ============================================================================

def initialize_embeddings(model_name: str) -> Any:
    """Initialize embedding model with M4 Pro optimizations."""

    logger.info(f"Loading embedding model: {model_name}")
    logger.info(f"Hardware: MacBook Pro M4 Pro (16 cores, 32GB RAM)")

    if "text-embedding" in model_name:
        # OpenAI embeddings
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI embeddings")

        return OpenAIEmbeddings(
            model=model_name,
            openai_api_key=config.openai_api_key
        )
    else:
        # Sentence Transformers (local, M4 Pro optimized)
        # Note: MPS (Metal Performance Shaders) not yet stable for sentence-transformers
        # Using CPU with optimized settings instead
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={
                'device': 'cpu',  # MPS support coming soon
            },
            encode_kwargs={
                'normalize_embeddings': True,
                'batch_size': config.batch_size,  # Large batches for M4 Pro
                'show_progress_bar': False  # We use tqdm instead
            }
        )


def embed_and_store(
    documents: List[Document],
    embeddings: Any,
    collection_name: str = "buddhist_texts",
    batch_size: int = 32,
    reset: bool = False
) -> None:
    """
    Generate embeddings and store in ChromaDB.

    Args:
        documents: List of Document objects to embed
        embeddings: Embedding model instance
        collection_name: Name of ChromaDB collection
        batch_size: Number of documents to process at once
        reset: If True, delete existing collection first
    """

    logger.info(f"Initializing ChromaDB at {config.chroma_db_path}")

    # Create ChromaDB client
    client = chromadb.PersistentClient(
        path=config.chroma_db_path,
        settings=ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )

    # Reset collection if requested
    if reset:
        logger.warning(f"Deleting existing collection: {collection_name}")
        try:
            client.delete_collection(collection_name)
        except Exception as e:
            logger.info(f"No existing collection to delete: {e}")

    # Create or get collection
    try:
        collection = client.get_collection(collection_name)
        logger.info(f"Using existing collection (current size: {collection.count()})")
    except Exception:
        logger.info(f"Creating new collection: {collection_name}")
        collection = client.create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:M": 32,
            }
        )

    # Process documents in batches
    logger.info(f"Embedding {len(documents)} document chunks in batches of {batch_size}")

    vectorstore = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings
    )

    # Add documents in batches with progress bar
    for i in tqdm(range(0, len(documents), batch_size), desc="Embedding batches"):
        batch = documents[i:i + batch_size]
        try:
            vectorstore.add_documents(batch)
        except Exception as e:
            logger.error(f"Error embedding batch {i // batch_size + 1}: {e}")

    # Final count
    final_collection = client.get_collection(collection_name)
    logger.info(f"✓ Embedding complete! Total documents in collection: {final_collection.count()}")


# ============================================================================
# Statistics & Validation
# ============================================================================

def print_statistics(documents: List[Dict[str, Any]], chunks: List[Document]) -> None:
    """Print statistics about the documents and chunks."""

    logger.info("=" * 80)
    logger.info("EMBEDDING STATISTICS")
    logger.info("=" * 80)

    # Document stats
    logger.info(f"Total documents: {len(documents)}")

    # Language distribution
    languages = {}
    for doc in documents:
        lang = doc.get("language", "unknown")
        languages[lang] = languages.get(lang, 0) + 1

    logger.info(f"Languages: {languages}")

    # Category distribution
    categories = {}
    for doc in documents:
        cat = doc.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    logger.info(f"Categories: {categories}")

    # Chunk stats
    logger.info(f"Total chunks: {len(chunks)}")
    logger.info(f"Average chunks per document: {len(chunks) / len(documents):.1f}")

    # Chunk size distribution
    chunk_sizes = [len(chunk.page_content) for chunk in chunks]
    avg_size = sum(chunk_sizes) / len(chunk_sizes)
    logger.info(f"Average chunk size: {avg_size:.0f} characters")

    logger.info("=" * 80)


# ============================================================================
# Main Script
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for Buddhist texts"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/",
        help="Input directory containing processed JSON files"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="buddhist_texts",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Embedding model name (overrides .env)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
        help="Batch size for embedding generation (default 128 for M4 Pro)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Number of worker processes (default 12 for M4 Pro 16-core)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum chunk size in characters"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Overlap between chunks"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing collection before embedding"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and chunk documents without embedding"
    )

    args = parser.parse_args()

    # Update config
    if args.model:
        config.embedding_model = args.model
    config.chunk_size = args.chunk_size
    config.chunk_overlap = args.chunk_overlap
    config.batch_size = args.batch_size

    logger.info("=" * 80)
    logger.info("BUDDHIST AI CHATBOT - EMBEDDING GENERATION (M4 PRO OPTIMIZED)")
    logger.info("=" * 80)
    logger.info(f"Input directory: {args.input}")
    logger.info(f"Collection name: {args.collection}")
    logger.info(f"Embedding model: {config.embedding_model}")
    logger.info(f"Chunk size: {config.chunk_size} chars")
    logger.info(f"Chunk overlap: {config.chunk_overlap} chars")
    logger.info(f"Batch size: {config.batch_size} (M4 Pro optimized)")
    logger.info(f"Workers: {args.workers}")
    logger.info(f"Hardware: MacBook Pro M4 Pro (16 cores, 32GB RAM)")
    logger.info("=" * 80)

    # Step 1: Load documents
    documents = load_documents_from_directory(args.input)

    if not documents:
        logger.error("No documents found. Exiting.")
        sys.exit(1)

    # Step 2: Chunk documents
    chunks = chunk_documents(
        documents,
        chunk_size=config.chunk_size,
        overlap=config.chunk_overlap
    )

    # Print statistics
    print_statistics(documents, chunks)

    if args.dry_run:
        logger.info("Dry run complete. Exiting without embedding.")
        return

    # Step 3: Initialize embeddings
    embeddings = initialize_embeddings(config.embedding_model)

    # Step 4: Embed and store
    embed_and_store(
        documents=chunks,
        embeddings=embeddings,
        collection_name=args.collection,
        batch_size=config.batch_size,
        reset=args.reset
    )

    logger.info("✅ Embedding process complete!")
    logger.info(f"You can now start the API server: uvicorn main:app --reload")


if __name__ == "__main__":
    main()
