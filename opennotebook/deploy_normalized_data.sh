#!/bin/bash
# deploy_normalized_data.sh
# Blue-Green deployment for normalized data
#
# Usage:
#   ./deploy_normalized_data.sh          # Deploy normalized data
#   ./deploy_normalized_data.sh --rollback  # Rollback to original

set -e

DATA_DIR="source_explorer/source_data"
ORIGINAL="source_summaries_ko.json"
NORMALIZED="source_summaries_ko_normalized.json"
OLD_SUFFIX=".old"

cd "$(dirname "$0")"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Tripitaka Data Deployment Script"
echo "========================================"

if [ "$1" == "--rollback" ]; then
    echo -e "${YELLOW}Rolling back to original data...${NC}"

    if [ ! -f "$DATA_DIR/${ORIGINAL}${OLD_SUFFIX}" ]; then
        echo -e "${RED}Error: Backup file not found. Cannot rollback.${NC}"
        exit 1
    fi

    # Swap back
    mv "$DATA_DIR/$ORIGINAL" "$DATA_DIR/$NORMALIZED"
    mv "$DATA_DIR/${ORIGINAL}${OLD_SUFFIX}" "$DATA_DIR/$ORIGINAL"

    echo -e "${GREEN}Rollback complete!${NC}"
    echo "  - Active: $ORIGINAL (original)"
    echo "  - Backup: $NORMALIZED"

else
    echo "Deploying normalized data..."

    # Verify files exist
    if [ ! -f "$DATA_DIR/$ORIGINAL" ]; then
        echo -e "${RED}Error: Original file not found: $DATA_DIR/$ORIGINAL${NC}"
        exit 1
    fi

    if [ ! -f "$DATA_DIR/$NORMALIZED" ]; then
        echo -e "${RED}Error: Normalized file not found: $DATA_DIR/$NORMALIZED${NC}"
        exit 1
    fi

    # Check if already deployed
    if [ -f "$DATA_DIR/${ORIGINAL}${OLD_SUFFIX}" ]; then
        echo -e "${YELLOW}Warning: Previous deployment detected. Old backup will be overwritten.${NC}"
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 1
        fi
        rm "$DATA_DIR/${ORIGINAL}${OLD_SUFFIX}"
    fi

    # Record counts for verification
    ORIG_COUNT=$(python3 -c "import json; print(len(json.load(open('$DATA_DIR/$ORIGINAL'))['summaries']))")
    NORM_COUNT=$(python3 -c "import json; print(len(json.load(open('$DATA_DIR/$NORMALIZED'))['summaries']))")

    echo "  Original records: $ORIG_COUNT"
    echo "  Normalized records: $NORM_COUNT"

    if [ "$ORIG_COUNT" != "$NORM_COUNT" ]; then
        echo -e "${RED}Error: Record count mismatch!${NC}"
        exit 1
    fi

    # Perform swap
    echo "Swapping files..."
    mv "$DATA_DIR/$ORIGINAL" "$DATA_DIR/${ORIGINAL}${OLD_SUFFIX}"
    mv "$DATA_DIR/$NORMALIZED" "$DATA_DIR/$ORIGINAL"

    echo -e "${GREEN}Deployment complete!${NC}"
    echo "  - Active: $ORIGINAL (normalized)"
    echo "  - Backup: ${ORIGINAL}${OLD_SUFFIX}"
    echo ""
    echo "To rollback: ./deploy_normalized_data.sh --rollback"
fi

echo ""
echo "Post-deployment checklist:"
echo "  [ ] Test search/filter on the web UI"
echo "  [ ] Verify period dropdown shows 14 categories"
echo "  [ ] Verify tradition dropdown shows 12 categories"
echo "  [ ] Check sample record displays correctly"
echo "========================================"
