"""Command-line interface for Buddhist RAG System.

This module provides CLI commands to process CBETA texts and query the system.

Examples:
    ```bash
    # Embed CBETA T/ folder
    python -m src.cli embed --input data/cbeta-t --collection taisho_canon

    # Query the system
    python -m src.cli query "What are the Four Noble Truths?"

    # Start API server
    python -m src.cli serve --port 8000
    ```
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.answerer import Answerer, AnswererConfig
from src.chunker import TEIChunker, ChunkerConfig
from src.embedder import Embedder, EmbedderConfig
from src.retriever import Retriever, RetrieverConfig
from src.vectordb import VectorDB, VectorDBConfig

# Load environment variables
load_dotenv()

# Rich console for pretty output
console = Console()


@click.group()
@click.version_option()
def cli():
    """Buddhist RAG System - CLI for CBETA Taishō Canon.

    Process Buddhist texts and query using AI-powered retrieval.
    """
    pass


@cli.command()
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to CBETA T/ folder with XML files",
)
@click.option(
    "--collection",
    "-c",
    default="taisho_canon",
    help="ChromaDB collection name",
)
@click.option(
    "--persist-dir",
    "-p",
    default="./data/chroma_db",
    help="ChromaDB persist directory",
)
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["openai", "local"]),
    default="openai",
    help="Embedding backend (openai or local)",
)
@click.option(
    "--batch-size",
    default=100,
    help="Number of chunks to process in one batch",
)
def embed(
    input: Path,
    collection: str,
    persist_dir: str,
    backend: str,
    batch_size: int,
):
    """Process CBETA XML files and store embeddings in vector database.

    This command:
    1. Parses TEI P5 XML files from CBETA T/ folder
    2. Extracts text chunks with metadata
    3. Generates embeddings
    4. Stores in ChromaDB for retrieval

    Example:
        python -m src.cli embed -i data/cbeta-t -c taisho_canon
    """
    console.print(f"\n[bold blue]Starting embedding process...[/bold blue]")
    console.print(f"Input: {input}")
    console.print(f"Collection: {collection}")
    console.print(f"Backend: {backend}\n")

    try:
        # Initialize components
        console.print("[yellow]Initializing components...[/yellow]")

        chunker_config = ChunkerConfig()
        chunker = TEIChunker(config=chunker_config)

        embedder_config = EmbedderConfig(
            backend=backend,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            local_model=os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3"),
            embedding_dim=1024 if backend == "local" else 1536,
            batch_size=batch_size,
        )
        embedder = Embedder.from_config(embedder_config)

        vectordb_config = VectorDBConfig(
            collection_name=collection,
            persist_directory=persist_dir,
        )
        vectordb = VectorDB.from_config(vectordb_config)

        # Find all XML files
        xml_files = list(input.rglob("*.xml"))
        console.print(f"[green]Found {len(xml_files)} XML files[/green]\n")

        if not xml_files:
            console.print("[red]No XML files found![/red]")
            sys.exit(1)

        # Process files with progress bar
        total_chunks = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing files...", total=len(xml_files))

            for xml_file in xml_files:
                try:
                    # Parse and chunk
                    chunks = chunker(xml_file)

                    if chunks:
                        # Prepare chunk data
                        chunk_dicts = [
                            {"text": chunk.text, "metadata": chunk.metadata}
                            for chunk in chunks
                        ]

                        # Generate embeddings
                        texts = [chunk.text for chunk in chunks]
                        embeddings = embedder(texts)

                        # Store in vectordb
                        vectordb.add_chunks(chunk_dicts, embeddings)

                        total_chunks += len(chunks)
                        progress.console.print(
                            f"[dim]  {xml_file.name}: {len(chunks)} chunks[/dim]"
                        )

                except Exception as e:
                    progress.console.print(
                        f"[red]  Error processing {xml_file.name}: {e}[/red]"
                    )

                progress.update(task, advance=1)

        # Summary
        stats = vectordb.get_stats()
        console.print(f"\n[bold green]✓ Embedding complete![/bold green]")
        console.print(f"Total chunks stored: {stats['count']}")
        console.print(f"Collection: {stats['collection_name']}\n")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option(
    "--collection",
    "-c",
    default="taisho_canon",
    help="ChromaDB collection name",
)
@click.option(
    "--persist-dir",
    "-p",
    default="./data/chroma_db",
    help="ChromaDB persist directory",
)
@click.option(
    "--top-k",
    "-k",
    default=5,
    help="Number of results to retrieve",
)
@click.option(
    "--llm-backend",
    "-l",
    type=click.Choice(["openai", "claude"]),
    default="openai",
    help="LLM backend for answer generation",
)
@click.option(
    "--show-sources/--no-sources",
    default=True,
    help="Show source citations",
)
def query(
    query: str,
    collection: str,
    persist_dir: str,
    top_k: int,
    llm_backend: str,
    show_sources: bool,
):
    """Query the Buddhist RAG system.

    Ask questions about Buddhist teachings and get answers with sources.

    Example:
        python -m src.cli query "What are the Four Noble Truths?"
        python -m src.cli query "사성제란 무엇입니까?" -k 3
    """
    console.print(f"\n[bold blue]Query:[/bold blue] {query}\n")

    try:
        # Initialize components
        with console.status("[yellow]Initializing RAG pipeline...[/yellow]"):
            # Embedder
            embedder_config = EmbedderConfig(
                backend=os.getenv("EMBEDDER_BACKEND", "openai"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
            )
            embedder = Embedder.from_config(embedder_config)

            # VectorDB
            vectordb_config = VectorDBConfig(
                collection_name=collection,
                persist_directory=persist_dir,
            )
            vectordb = VectorDB.from_config(vectordb_config)

            # Retriever
            retriever_config = RetrieverConfig(top_k=top_k)
            retriever = Retriever(embedder, vectordb, retriever_config)

            # Answerer
            answerer_config = AnswererConfig(
                llm_backend=llm_backend,
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                claude_api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
            answerer = Answerer.from_config(answerer_config)

        # Retrieve relevant chunks
        with console.status("[yellow]Searching texts...[/yellow]"):
            results = retriever.retrieve(query)

        if not results:
            console.print("[yellow]No relevant texts found.[/yellow]\n")
            sys.exit(0)

        console.print(f"[green]Found {len(results)} relevant passages[/green]\n")

        # Generate answer
        with console.status("[yellow]Generating answer...[/yellow]"):
            response = answerer.answer(query, results)

        # Display answer
        console.print("[bold cyan]Answer:[/bold cyan]")
        console.print(f"{response.answer}\n")

        # Display sources if requested
        if show_sources and response.sources:
            table = Table(title="Sources", show_header=True)
            table.add_column("Rank", style="cyan", width=6)
            table.add_column("Score", style="green", width=8)
            table.add_column("Sutra ID", style="yellow", width=12)
            table.add_column("Text Preview", style="white")

            for source in response.sources[:top_k]:
                table.add_row(
                    str(source.rank),
                    f"{source.score:.3f}",
                    source.metadata.get("sutra_id", "N/A"),
                    source.text[:80] + "..." if len(source.text) > 80 else source.text,
                )

            console.print(table)

        console.print(f"\n[dim]Tokens used: {response.tokens_used}[/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--host",
    "-h",
    default="0.0.0.0",
    help="Host to bind to",
)
@click.option(
    "--port",
    "-p",
    default=8000,
    help="Port to bind to",
)
@click.option(
    "--reload/--no-reload",
    default=True,
    help="Enable auto-reload",
)
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI server.

    Launch the REST API for querying the system via HTTP.

    Example:
        python -m src.cli serve --port 8000
    """
    import uvicorn

    console.print(f"\n[bold blue]Starting API server...[/bold blue]")
    console.print(f"Host: {host}")
    console.print(f"Port: {port}")
    console.print(f"Docs: http://{host}:{port}/docs\n")

    uvicorn.run(
        "src.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command()
@click.option(
    "--collection",
    "-c",
    default="taisho_canon",
    help="ChromaDB collection name",
)
@click.option(
    "--persist-dir",
    "-p",
    default="./data/chroma_db",
    help="ChromaDB persist directory",
)
def stats(collection: str, persist_dir: str):
    """Show database statistics.

    Display information about the vector database collection.

    Example:
        python -m src.cli stats
    """
    try:
        vectordb_config = VectorDBConfig(
            collection_name=collection,
            persist_directory=persist_dir,
        )
        vectordb = VectorDB.from_config(vectordb_config)

        stats = vectordb.get_stats()

        table = Table(title="Database Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Collection Name", stats["collection_name"])
        table.add_row("Document Count", str(stats["count"]))
        table.add_row("Distance Metric", stats["distance_metric"])
        table.add_row("Persist Directory", persist_dir)

        console.print()
        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
