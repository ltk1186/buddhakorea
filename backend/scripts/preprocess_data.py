"""
Data Preprocessing Utility for Buddhist Texts

Converts raw Buddhist texts (CBETA XML, plain text, HTML) into JSON format
for embedding generation.

Usage:
    # Process CBETA XML files
    python scripts/preprocess_data.py --input data/raw/cbeta/ --output data/processed/chinese/ --format xml

    # Process plain text files
    python scripts/preprocess_data.py --input data/raw/pali/ --output data/processed/english/ --format txt

    # Process HTML from SuttaCentral
    python scripts/preprocess_data.py --input data/raw/suttacentral/ --output data/processed/english/ --format html
"""

import os
import json
import argparse
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from tqdm import tqdm
from loguru import logger


# ============================================================================
# Text Cleaning
# ============================================================================

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Remove excessive blank lines
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    return text.strip()


# ============================================================================
# Format-Specific Parsers
# ============================================================================

def parse_cbeta_xml(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse CBETA TEI P5 XML file.

    CBETA XML structure:
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader>
        <fileDesc>
          <titleStmt><title>經典標題</title></titleStmt>
          <publicationStmt>
            <idno type="CBETA">T01n0001</idno>
          </publicationStmt>
        </fileDesc>
      </teiHeader>
      <text>
        <body>
          <div type="jing">
            <p>經文內容...</p>
            <lg><l>偈頌內容...</l></lg>
          </div>
        </body>
      </text>
    </TEI>
    """

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # TEI P5 namespace
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

        # Extract metadata from header
        title_elem = root.find('.//tei:titleStmt/tei:title', ns)
        title = title_elem.text if title_elem is not None and title_elem.text else file_path.stem

        # Get CBETA ID from root element's xml:id attribute (e.g., T42n1828)
        # Note: xml:id is in the XML namespace, not TEI
        text_id = root.get('{http://www.w3.org/XML/1998/namespace}id')
        if not text_id:
            # Fallback to old method if xml:id doesn't exist
            idno_elem = root.find('.//tei:publicationStmt/tei:idno[@type="CBETA"]', ns)
            text_id = idno_elem.text if idno_elem is not None else file_path.stem

        # Apply T85 filtering strategy
        if not should_include_text(text_id):
            logger.debug(f"Skipping {text_id} based on filtering rules")
            return None

        # Determine category from volume prefix
        volume = text_id[:3] if len(text_id) >= 3 else "T00"
        category = categorize_volume(volume)

        # Extract text from body
        body = root.find('.//tei:body', ns)
        if body is None:
            logger.warning(f"No body found in {file_path}")
            return None

        # Extract text, filtering out notes and apparatus
        text_parts = []
        for elem in body.iter():
            # Skip notes, line breaks, page breaks, and apparatus
            if elem.tag in [f'{{{ns["tei"]}}}note', f'{{{ns["tei"]}}}lb',
                            f'{{{ns["tei"]}}}pb', f'{{{ns["tei"]}}}app']:
                continue

            # Get text content
            if elem.text:
                text_parts.append(elem.text)
            if elem.tail:
                text_parts.append(elem.tail)

        text = ' '.join(text_parts)
        text = clean_text(text)

        if not text or len(text) < 50:
            logger.warning(f"Text too short in {file_path}: {len(text)} chars")
            return None

        # Get juan (fascicle) number if available
        juan_elem = root.find('.//tei:div[@type="juan"]', ns)
        juan = juan_elem.get('n') if juan_elem is not None else "1"

        return {
            "text_id": text_id,
            "title": title,
            "language": "zh",
            "category": category,
            "source": "cbeta",
            "translator": "",
            "text": text,
            "metadata": {
                "filename": file_path.name,
                "format": "xml",
                "volume": volume,
                "juan": juan,
                "file_path": str(file_path)
            }
        }

    except Exception as e:
        logger.error(f"Error parsing CBETA XML {file_path}: {e}")
        return None


def should_include_text(text_id: str) -> bool:
    """
    Determine if a CBETA text should be included based on T85 filtering strategy.

    Inclusion rules:
    - T01-T55: Include ALL (2,279 texts) - core canonical texts
    - T85 (T2821-T2920): Selective inclusion
      - Include T2732-T2856: High-value commentaries and practice texts
      - Include T2887: 父母恩重經 (cultural significance in Korean Buddhism)
      - Include T2898: 高王觀世音經 (important in popular Buddhism)
      - Exclude T2857-T2864: Literary works (變文, poems)
      - Exclude T2865-T2886, T2888-T2897, T2899-T2920: Apocryphal sutras

    Returns:
        True if text should be included, False otherwise
    """
    # Extract text number from CBETA ID
    # Format can be: T42n1828 (volume + n + text_num) or T1828 (just text_num)
    # We want the number after 'n' if it exists, otherwise the number after 'T'
    match = re.match(r'T\d+n(\d+)', text_id)  # Match T42n1828 format
    if not match:
        match = re.match(r'T(\d+)', text_id)  # Fallback to T1828 format

    if not match:
        logger.warning(f"Could not parse text ID: {text_id}")
        return False

    text_num = int(match.group(1))

    # T01-T55: Include all
    if 1 <= text_num <= 2920 and text_num < 2821:
        return True

    # T85 filtering (T2821-T2920)
    if 2821 <= text_num <= 2920:
        # Include commentaries and practice texts
        if 2732 <= text_num <= 2856:
            return True
        # Include culturally significant texts
        if text_num == 2887:  # 父母恩重經
            return True
        if text_num == 2898:  # 高王觀世音經
            return True
        # Exclude all others (literary works + apocryphal sutras)
        logger.info(f"Excluding T85 text {text_id} (literary/apocryphal)")
        return False

    # Include everything else
    return True


def categorize_volume(volume: str) -> str:
    """
    Categorize text by Taishō volume number.

    Volume ranges:
    - T01-T04: Āgama (阿含部)
    - T05-T07: Jātaka, Avadāna (本緣部)
    - T08-T13: Mahāyāna Sūtras (大乘經典)
    - T14-T21: Prajñāpāramitā (般若部)
    - T22-T23: Saddharmapuṇḍarīka, etc. (法華部等)
    - T24-T29: Ratnakūṭa, Buddhāvataṃsaka (寶積部、華嚴部)
    - T30-T39: Nirvāṇa, Tantra (涅槃部、密教部)
    - T40-T48: Commentaries (經疏部)
    - T49-T52: Vinaya (律部)
    - T53-T55: Abhidharma (毘曇部)
    - T56-T60: Śāstra (論集部)
    - T61-T84: Chinese Buddhist texts (中國撰述)
    - T85: Miscellaneous (疑偽部) - filtered by should_include_text()
    """

    vol_num = int(volume[1:]) if len(volume) > 1 else 0

    if 1 <= vol_num <= 4:
        return "agama"
    elif 5 <= vol_num <= 7:
        return "jataka"
    elif 8 <= vol_num <= 13:
        return "mahayana"
    elif 14 <= vol_num <= 23:
        return "prajna"
    elif 24 <= vol_num <= 39:
        return "mahayana"
    elif 40 <= vol_num <= 48:
        return "commentary"
    elif 49 <= vol_num <= 52:
        return "vinaya"
    elif 53 <= vol_num <= 60:
        return "abhidharma"
    elif 61 <= vol_num <= 84:
        return "chinese_buddhist"
    else:
        return "miscellaneous"


def parse_html(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse HTML file (e.g., from SuttaCentral).

    Expected structure:
    <article>
      <header><h1>Sutta Title</h1></header>
      <div class="sutta-text">Text content...</div>
    </article>
    """

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'lxml')

        # Extract title
        title_elem = soup.find('h1')
        title = title_elem.get_text() if title_elem else file_path.stem

        # Extract text content (remove scripts, styles)
        for script in soup(["script", "style"]):
            script.decompose()

        # Get main content
        article = soup.find('article') or soup.find('div', class_='sutta-text') or soup.body
        if article is None:
            logger.warning(f"No main content found in {file_path}")
            return None

        text = article.get_text(separator='\n')
        text = clean_text(text)

        # Try to extract sutta ID from filename (e.g., mn1_en.html -> MN1)
        text_id = file_path.stem.upper().replace('_EN', '').replace('_', '')

        return {
            "text_id": text_id,
            "title": title,
            "language": "en",
            "category": "sutta",
            "source": "suttacentral",
            "translator": "",
            "text": text,
            "metadata": {
                "filename": file_path.name,
                "format": "html"
            }
        }

    except Exception as e:
        logger.error(f"Error parsing HTML {file_path}: {e}")
        return None


def parse_txt(file_path: Path, language: str = "en") -> Optional[Dict[str, Any]]:
    """
    Parse plain text file.

    Expected format:
    First line: Title
    Second line: Text ID (optional)
    Rest: Content

    Or just plain content (title = filename)
    """

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')

        # Try to parse structured format
        if len(lines) >= 2 and len(lines[0]) < 200:  # First line looks like title
            title = lines[0].strip()
            if lines[1].strip() and len(lines[1]) < 50:  # Second line looks like ID
                text_id = lines[1].strip()
                text = '\n'.join(lines[2:])
            else:
                text_id = file_path.stem
                text = '\n'.join(lines[1:])
        else:
            # Just use filename as title
            title = file_path.stem.replace('_', ' ').title()
            text_id = file_path.stem
            text = content

        text = clean_text(text)

        return {
            "text_id": text_id,
            "title": title,
            "language": language,
            "category": "sutta",
            "source": "plain_text",
            "translator": "",
            "text": text,
            "metadata": {
                "filename": file_path.name,
                "format": "txt"
            }
        }

    except Exception as e:
        logger.error(f"Error parsing text file {file_path}: {e}")
        return None


# ============================================================================
# Batch Processing
# ============================================================================

def process_directory(
    input_dir: Path,
    output_dir: Path,
    file_format: str,
    language: str = "auto"
) -> None:
    """
    Process all files in a directory.

    Args:
        input_dir: Directory containing raw files
        output_dir: Directory for processed JSON files
        file_format: File format (xml, html, txt)
        language: Language code (auto, zh, en, ko)
    """

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all files with the specified format
    if file_format == "xml":
        files = list(input_dir.rglob("*.xml"))
        parser = parse_cbeta_xml
    elif file_format == "html":
        files = list(input_dir.rglob("*.html")) + list(input_dir.rglob("*.htm"))
        parser = parse_html
    elif file_format == "txt":
        files = list(input_dir.rglob("*.txt"))
        parser = lambda f: parse_txt(f, language=language)
    else:
        logger.error(f"Unsupported format: {file_format}")
        return

    logger.info(f"Found {len(files)} {file_format} files in {input_dir}")

    if not files:
        logger.warning("No files found to process")
        return

    # Process each file
    success_count = 0
    for file_path in tqdm(files, desc=f"Processing {file_format} files"):
        result = parser(file_path)

        if result:
            # Save as JSON
            output_file = output_dir / f"{result['text_id']}.json"

            # Avoid overwriting (add suffix if exists)
            counter = 1
            while output_file.exists():
                output_file = output_dir / f"{result['text_id']}_{counter}.json"
                counter += 1

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            success_count += 1

    logger.info(f"✓ Successfully processed {success_count}/{len(files)} files")
    logger.info(f"Output saved to: {output_dir}")


# ============================================================================
# Main Script
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Preprocess Buddhist texts for embedding"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input directory containing raw files"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for processed JSON files"
    )
    parser.add_argument(
        "--format",
        type=str,
        required=True,
        choices=["xml", "html", "txt"],
        help="Input file format"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="auto",
        choices=["auto", "zh", "en", "ko"],
        help="Language code (for txt format)"
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return

    logger.info("=" * 80)
    logger.info("BUDDHIST TEXT PREPROCESSING")
    logger.info("=" * 80)
    logger.info(f"Input: {input_dir}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Format: {args.format}")
    logger.info(f"Language: {args.language}")
    logger.info("=" * 80)

    process_directory(input_dir, output_dir, args.format, args.language)

    logger.info("✅ Preprocessing complete!")


if __name__ == "__main__":
    main()
