"""
Extract Buddhist Source Catalog from ChromaDB
Scans all documents and creates a catalog of unique texts with metadata
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")


def extract_sample_text_from_xml(xml_path: str, max_chars: int = 2000) -> str:
    """
    Extract first max_chars of text content from TEI XML file for context.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Find all text nodes (handling TEI namespace)
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        text_elements = root.findall('.//tei:p', ns) or root.findall('.//p')

        # Collect text content
        text_parts = []
        total_length = 0

        for elem in text_elements:
            if total_length >= max_chars:
                break
            text = ''.join(elem.itertext()).strip()
            if text:
                text_parts.append(text)
                total_length += len(text)

        sample = ' '.join(text_parts)[:max_chars]
        return sample

    except Exception as e:
        logger.warning(f"Could not extract text from {xml_path}: {e}")
        return ""


def extract_sources_from_chroma(
    chroma_path: str,
    collection_name: str,
    xml_base_path: str,
    output_path: str
):
    """
    Extract all unique sources from ChromaDB collection.
    """
    logger.info(f"Connecting to ChromaDB at {chroma_path}")

    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=False
        )
    )

    collection = client.get_collection(collection_name)
    total_docs = collection.count()

    logger.info(f"Total documents in collection: {total_docs:,}")
    logger.info("Scanning for unique sources...")

    sources = {}
    batch_size = 1000

    # Scan all documents to find unique sources
    for offset in range(0, total_docs, batch_size):
        logger.info(f"Processing batch {offset // batch_size + 1}/{(total_docs // batch_size) + 1}")

        results = collection.get(
            limit=batch_size,
            offset=offset,
            include=['metadatas']
        )

        for metadata in results['metadatas']:
            sutra_id = metadata.get('sutra_id')

            if not sutra_id or sutra_id in sources:
                continue

            # Store source metadata
            sources[sutra_id] = {
                'sutra_id': sutra_id,
                'title': metadata.get('title', 'Unknown'),
                'author': metadata.get('author', 'Unknown'),
                'volume': metadata.get('volume', 'Unknown'),
                'number': metadata.get('number', 'Unknown'),
                'juan': metadata.get('juan', 'Unknown'),
                'file_path': metadata.get('file_path', ''),
                'total_chunks': metadata.get('total_chunks', 0)
            }

    logger.info(f"Found {len(sources)} unique sources")

    # Extract sample text for each source
    logger.info("Extracting sample texts from XML files...")

    for i, (sutra_id, source) in enumerate(sources.items()):
        if (i + 1) % 50 == 0:
            logger.info(f"Processed {i + 1}/{len(sources)} sources")

        xml_path = source.get('file_path')

        if xml_path and os.path.exists(xml_path):
            sample_text = extract_sample_text_from_xml(xml_path, max_chars=2000)
            source['sample_text'] = sample_text
        else:
            source['sample_text'] = ""

    # Sort sources by sutra_id
    sorted_sources = dict(sorted(sources.items()))

    # Save to JSON
    logger.info(f"Saving catalog to {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_sources': len(sorted_sources),
            'total_documents': total_docs,
            'sources': sorted_sources
        }, f, ensure_ascii=False, indent=2)

    logger.info("✓ Source catalog extraction complete!")
    logger.info(f"  Total sources: {len(sorted_sources)}")
    logger.info(f"  Output file: {output_path}")

    return sorted_sources


if __name__ == "__main__":
    # Configuration
    CHROMA_PATH = "../chroma_db"
    COLLECTION_NAME = "cbeta_sutras_finetuned"
    XML_BASE_PATH = "../data/raw/cbeta"
    OUTPUT_PATH = "source_data/source_catalog.json"

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Extract sources
    sources = extract_sources_from_chroma(
        chroma_path=CHROMA_PATH,
        collection_name=COLLECTION_NAME,
        xml_base_path=XML_BASE_PATH,
        output_path=OUTPUT_PATH
    )

    # Print sample
    logger.info("\nSample of extracted sources:")
    for i, (sutra_id, info) in enumerate(list(sources.items())[:5]):
        logger.info(f"{i+1}. {sutra_id}: {info['title']}")
        logger.info(f"   Author: {info['author']}")
        logger.info(f"   Volume: {info['volume']} | Juan: {info['juan']}")
        logger.info(f"   Sample text length: {len(info['sample_text'])} chars")
        logger.info("")
