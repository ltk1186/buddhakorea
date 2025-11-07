"""
CBETA Taishō Tripiṭaka Downloader

Downloads CBETA XML corpus from GitHub repository.
Supports full clone or selective volume download.

Usage:
    # Download full Taishō Tripiṭaka
    python scripts/download_cbeta.py --full

    # Download specific volumes
    python scripts/download_cbeta.py --volumes T01 T08 T12

    # Download volume range
    python scripts/download_cbeta.py --volumes T01-T13
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from loguru import logger
import time


# Use cbeta-git/xml-p5a (latest internal version with T0001-T2920)
# NOT cbeta-org/xml-p5 (older, only ~3000 texts)
CBETA_GITHUB_REPO = "https://github.com/cbeta-git/xml-p5a.git"
DEFAULT_OUTPUT_DIR = "data/raw/cbeta"


def clone_full_repo(output_dir: Path, shallow: bool = True) -> bool:
    """
    Clone the full CBETA repository.

    Args:
        output_dir: Directory to clone into
        shallow: If True, do shallow clone (faster, less disk)

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Cloning CBETA repository to {output_dir}")
    logger.info(f"Repository: {CBETA_GITHUB_REPO}")
    logger.info(f"Size: ~10-15GB (this may take 2-3 hours depending on connection)")

    output_dir.parent.mkdir(parents=True, exist_ok=True)

    if output_dir.exists():
        logger.warning(f"Directory {output_dir} already exists")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            logger.info("Cancelled by user")
            return False

        logger.info(f"Removing existing directory: {output_dir}")
        subprocess.run(["rm", "-rf", str(output_dir)], check=True)

    # Build clone command
    cmd = ["git", "clone"]

    if shallow:
        logger.info("Performing shallow clone (--depth 1)")
        cmd.extend(["--depth", "1"])

    cmd.extend([CBETA_GITHUB_REPO, str(output_dir)])

    # Execute clone
    logger.info(f"Executing: {' '.join(cmd)}")
    start_time = time.time()

    try:
        subprocess.run(cmd, check=True)
        elapsed = time.time() - start_time
        logger.info(f"✓ Clone completed in {elapsed/60:.1f} minutes")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Clone failed: {e}")
        return False


def sparse_checkout_volumes(output_dir: Path, volumes: list[str]) -> bool:
    """
    Clone repository with sparse checkout for specific volumes.
    This is faster than cloning everything and then deleting.

    Args:
        output_dir: Directory to clone into
        volumes: List of volume codes (e.g., ['T01', 'T08'])

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Cloning CBETA with sparse checkout for volumes: {volumes}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)

    if output_dir.exists():
        logger.warning(f"Directory {output_dir} already exists")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            logger.info("Cancelled by user")
            return False

        subprocess.run(["rm", "-rf", str(output_dir)], check=True)

    try:
        # Initialize repo
        logger.info("Initializing git repository...")
        subprocess.run(["git", "init", str(output_dir)], check=True)

        # Change to repo directory
        os.chdir(output_dir)

        # Configure sparse checkout
        logger.info("Configuring sparse checkout...")
        subprocess.run(["git", "config", "core.sparseCheckout", "true"], check=True)

        # Add remote
        subprocess.run(["git", "remote", "add", "origin", CBETA_GITHUB_REPO], check=True)

        # Write sparse checkout patterns
        sparse_file = Path(".git/info/sparse-checkout")
        sparse_file.parent.mkdir(parents=True, exist_ok=True)

        with open(sparse_file, 'w') as f:
            for volume in volumes:
                f.write(f"{volume}/\n")
                logger.info(f"  Added pattern: {volume}/")

        # Pull specific volumes
        logger.info("Pulling selected volumes...")
        start_time = time.time()
        subprocess.run(["git", "pull", "--depth=1", "origin", "master"], check=True)
        elapsed = time.time() - start_time

        logger.info(f"✓ Sparse checkout completed in {elapsed/60:.1f} minutes")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Sparse checkout failed: {e}")
        return False


def parse_volume_range(volume_str: str) -> list[str]:
    """
    Parse volume specification.

    Examples:
        'T01' -> ['T01']
        'T01-T04' -> ['T01', 'T02', 'T03', 'T04']
        'T01,T08,T12' -> ['T01', 'T08', 'T12']
    """
    volumes = []

    # Handle comma-separated list
    if ',' in volume_str:
        return [v.strip() for v in volume_str.split(',')]

    # Handle range (T01-T04)
    if '-' in volume_str:
        start, end = volume_str.split('-')
        start_num = int(start[1:])  # Remove 'T' prefix
        end_num = int(end[1:])

        for i in range(start_num, end_num + 1):
            volumes.append(f"T{i:02d}")

        return volumes

    # Single volume
    return [volume_str]


def main():
    parser = argparse.ArgumentParser(
        description="Download CBETA Taishō Tripiṭaka XML from GitHub"
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Download full CBETA corpus (~10-15GB)"
    )

    parser.add_argument(
        "--volumes",
        nargs="+",
        help="Specific volumes to download (e.g., T01 T08 or T01-T13)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        "--no-shallow",
        action="store_true",
        help="Perform full clone instead of shallow (includes git history)"
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    shallow = not args.no_shallow

    logger.info("=" * 80)
    logger.info("CBETA TAISHŌ TRIPIṬAKA DOWNLOADER")
    logger.info("=" * 80)
    logger.info(f"Output directory: {output_dir.absolute()}")

    if not args.full and not args.volumes:
        logger.error("Must specify either --full or --volumes")
        logger.info("\nExamples:")
        logger.info("  python scripts/download_cbeta.py --full")
        logger.info("  python scripts/download_cbeta.py --volumes T01 T08")
        logger.info("  python scripts/download_cbeta.py --volumes T01-T13")
        sys.exit(1)

    # Full clone
    if args.full:
        logger.info("Mode: Full repository clone")
        success = clone_full_repo(output_dir, shallow=shallow)

    # Sparse checkout for specific volumes
    else:
        # Parse all volume specifications
        all_volumes = []
        for vol_spec in args.volumes:
            all_volumes.extend(parse_volume_range(vol_spec))

        # Remove duplicates and sort
        all_volumes = sorted(set(all_volumes))

        logger.info(f"Mode: Sparse checkout for {len(all_volumes)} volumes")
        logger.info(f"Volumes: {', '.join(all_volumes)}")

        success = sparse_checkout_volumes(output_dir, all_volumes)

    if success:
        logger.info("=" * 80)
        logger.info("✅ DOWNLOAD COMPLETE")
        logger.info("=" * 80)

        # Count XML files
        xml_files = list(output_dir.rglob("*.xml"))
        logger.info(f"Total XML files: {len(xml_files)}")

        # Show directory structure
        logger.info("\nDirectory structure:")
        try:
            subprocess.run(["tree", "-L", "2", str(output_dir)])
        except FileNotFoundError:
            # tree command not available
            logger.info(f"Contents: {list(output_dir.iterdir())[:10]}")

        logger.info(f"\nNext step:")
        logger.info(f"  python scripts/preprocess_data.py --input {output_dir} --output data/processed/")
    else:
        logger.error("Download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
