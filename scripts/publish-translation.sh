#!/usr/bin/env bash
# Completed content only: this command never imports model/provider clients.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
    echo "Usage: $0 {validate|import|publish|unpublish|status} ARTIFACT RELEASE SHA256 [publication-v1|dhammapada]" >&2
    exit 2
fi
COMMAND="$1"
ARTIFACT="$(realpath "$2")"
RELEASE="$3"
DIGEST="$4"
FORMAT="${5:-publication-v1}"
[[ "$COMMAND" =~ ^(validate|import|publish|unpublish|status)$ ]] || exit 2
[[ "$DIGEST" =~ ^[0-9a-f]{64}$ ]] || exit 2
test -f "$ARTIFACT"
test -f "$ROOT/.env"
docker compose --env-file "$ROOT/.env" -f "$ROOT/config/docker-compose.yml" \
    run --rm --no-deps --user 0:0 \
    -v "$ARTIFACT:/publication/artifact.json:ro" backend \
    python -m pali.scripts.publish_translation "$COMMAND" \
    --artifact /publication/artifact.json --format "$FORMAT" \
    --release "$RELEASE" --expected-sha256 "$DIGEST" --target production
