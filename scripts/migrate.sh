#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/config/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Missing $ENV_FILE"
    exit 1
fi

if [ $# -eq 0 ]; then
    set -- upgrade head
fi

docker compose \
    --profile tools \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    run --rm --no-deps migrate "$@"
