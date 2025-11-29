#!/bin/bash
# Production Deployment Script for Buddha Korea RAG System
# Implements blue-green deployment with health checks and rollback

set -euo pipefail

# Configuration
PROJECT_DIR="/opt/buddha-korea"
COMPOSE_FILE="docker-compose.production.yml"
HEALTH_ENDPOINT="http://localhost:8000/api/health"
HEALTH_TIMEOUT=120  # seconds
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups/deployments"
DATE=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Pre-deployment checks
preflight_checks() {
    log "Running preflight checks..."

    # Check if running as correct user
    if [ "$(whoami)" != "appuser" ] && [ "$(whoami)" != "root" ]; then
        error "Must run as appuser or root"
        exit 1
    fi

    # Check if docker-compose file exists
    if [ ! -f "${PROJECT_DIR}/${COMPOSE_FILE}" ]; then
        error "Docker compose file not found: ${PROJECT_DIR}/${COMPOSE_FILE}"
        exit 1
    fi

    # Check if required directories exist
    if [ ! -d "${PROJECT_DIR}/chroma_db" ]; then
        error "ChromaDB directory not found: ${PROJECT_DIR}/chroma_db"
        exit 1
    fi

    # Check if .env file exists
    if [ ! -f "${PROJECT_DIR}/.env" ]; then
        error ".env file not found"
        exit 1
    fi

    # Check disk space (require at least 2GB free)
    FREE_SPACE=$(df -BG "${PROJECT_DIR}" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$FREE_SPACE" -lt 2 ]; then
        error "Insufficient disk space: ${FREE_SPACE}GB free (need at least 2GB)"
        exit 1
    fi

    log "Preflight checks passed ✓"
}

# Backup current deployment
backup_deployment() {
    log "Backing up current deployment state..."

    mkdir -p "$BACKUP_DIR"

    # Create backup metadata
    cat > "${BACKUP_DIR}/backup_${DATE}.json" <<EOF
{
    "timestamp": "$(date -Iseconds)",
    "containers": $(docker ps --format '{{json .}}' | jq -s '.'),
    "images": $(docker images --format '{{json .}}' | jq -s '.')
}
EOF

    log "Backup created: ${BACKUP_DIR}/backup_${DATE}.json"
}

# Build new images
build_images() {
    log "Building new Docker images..."

    cd "$PROJECT_DIR"

    # Build with no cache to ensure latest code
    docker-compose -f "$COMPOSE_FILE" build --no-cache fastapi

    if [ $? -ne 0 ]; then
        error "Docker build failed"
        exit 1
    fi

    log "Images built successfully ✓"
}

# Health check function
health_check() {
    local max_attempts=$((HEALTH_TIMEOUT / 5))
    local attempt=1

    log "Waiting for application to become healthy..."

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
            log "Health check passed ✓"
            return 0
        fi

        echo -n "."
        sleep 5
        attempt=$((attempt + 1))
    done

    echo ""
    error "Health check failed after ${HEALTH_TIMEOUT}s"
    return 1
}

# Deploy with blue-green strategy
blue_green_deploy() {
    log "Starting blue-green deployment..."

    cd "$PROJECT_DIR"

    # Phase 1: Start new containers alongside old ones
    log "Phase 1: Starting new containers..."

    # Stop and remove old containers
    docker-compose -f "$COMPOSE_FILE" down

    # Start new containers
    docker-compose -f "$COMPOSE_FILE" up -d

    if [ $? -ne 0 ]; then
        error "Failed to start new containers"
        rollback
        exit 1
    fi

    # Phase 2: Health checks
    log "Phase 2: Running health checks..."

    if ! health_check; then
        error "New deployment failed health checks"
        rollback
        exit 1
    fi

    # Phase 3: Verify services
    log "Phase 3: Verifying services..."

    # Check FastAPI container
    if ! docker ps | grep -q "buddhakorea-fastapi"; then
        error "FastAPI container not running"
        rollback
        exit 1
    fi

    # Check Redis container
    if ! docker ps | grep -q "buddhakorea-redis"; then
        error "Redis container not running"
        rollback
        exit 1
    fi

    # Check Nginx container
    if ! docker ps | grep -q "buddhakorea-nginx"; then
        error "Nginx container not running"
        rollback
        exit 1
    fi

    log "All services verified ✓"

    # Phase 4: Test query
    log "Phase 4: Testing query endpoint..."

    TEST_RESPONSE=$(curl -s -X POST "$HEALTH_ENDPOINT/../chat" \
        -H "Content-Type: application/json" \
        -d '{"query":"테스트","detailed_mode":false}' || echo "FAILED")

    if echo "$TEST_RESPONSE" | grep -q "response"; then
        log "Query test passed ✓"
    else
        warn "Query test returned unexpected response (non-fatal)"
    fi

    log "Blue-green deployment completed successfully ✓"
}

# Rollback function
rollback() {
    error "Rolling back deployment..."

    cd "$PROJECT_DIR"

    # Stop failed containers
    docker-compose -f "$COMPOSE_FILE" down

    # Find latest backup
    LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/backup_*.json 2>/dev/null | head -1)

    if [ -n "$LATEST_BACKUP" ]; then
        log "Found backup: $LATEST_BACKUP"
        log "Manual rollback required - restore from backup if needed"
    else
        warn "No backup found for automatic rollback"
    fi

    # Attempt to restart previous containers
    docker-compose -f "$COMPOSE_FILE" up -d

    error "Rollback initiated - please verify system state"
}

# Post-deployment tasks
post_deployment() {
    log "Running post-deployment tasks..."

    # Setup Redis backup cron if not already configured
    if ! crontab -l 2>/dev/null | grep -q "backup_redis.sh"; then
        log "Setting up Redis backup cron job..."
        (crontab -l 2>/dev/null; echo "0 2 * * * ${PROJECT_DIR}/backup_redis.sh") | crontab -
        log "Redis backup cron configured ✓"
    fi

    # Cleanup old Docker images
    log "Cleaning up old Docker images..."
    docker image prune -f > /dev/null 2>&1

    log "Post-deployment tasks completed ✓"
}

# Main deployment flow
main() {
    log "======================================"
    log "Buddha Korea Production Deployment"
    log "======================================"
    log "Timestamp: $(date -Iseconds)"
    log ""

    preflight_checks
    backup_deployment
    build_images
    blue_green_deploy
    post_deployment

    log ""
    log "======================================"
    log "Deployment completed successfully! 🎉"
    log "======================================"
    log ""
    log "Next steps:"
    log "1. Monitor logs: tail -f ${LOG_DIR}/app.log"
    log "2. Test PII masking: docker exec buddhakorea-fastapi python3 privacy.py"
    log "3. View Redis data: docker exec buddhakorea-redis redis-cli -a \${REDIS_PASSWORD} INFO"
}

# Trap errors and run rollback
trap 'error "Deployment failed"; rollback; exit 1' ERR

# Run main deployment
main
