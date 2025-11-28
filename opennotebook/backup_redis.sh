#!/bin/bash
# Redis Backup Script for Buddha Korea Analytics
# Run via cron: 0 2 * * * /opt/buddha-korea/backup_redis.sh

set -euo pipefail

# Configuration
BACKUP_DIR="/opt/buddha-korea/backups/redis"
REDIS_DATA_DIR="/opt/buddha-korea/redis-data"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="redis_backup_${DATE}.tar.gz"

# Logging
LOG_FILE="${BACKUP_DIR}/backup.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

log "Starting Redis backup..."

# Trigger Redis BGSAVE via docker exec
if docker ps | grep -q buddhakorea-redis; then
    log "Triggering BGSAVE..."
    docker exec buddhakorea-redis redis-cli -a "${REDIS_PASSWORD:-changeme}" BGSAVE

    # Wait for BGSAVE to complete (check every 2 seconds, max 60 seconds)
    for i in {1..30}; do
        SAVE_STATUS=$(docker exec buddhakorea-redis redis-cli -a "${REDIS_PASSWORD:-changeme}" LASTSAVE)
        if [ -n "$SAVE_STATUS" ]; then
            log "BGSAVE completed at timestamp: $SAVE_STATUS"
            break
        fi
        sleep 2
    done
else
    log "ERROR: Redis container not running"
    exit 1
fi

# Create compressed backup
log "Creating compressed backup: $BACKUP_FILE"
cd "$REDIS_DATA_DIR"
tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" dump.rdb appendonly.aof

# Verify backup
if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    log "Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    log "ERROR: Backup file not created"
    exit 1
fi

# Remove old backups
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "redis_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "redis_backup_*.tar.gz" -type f | wc -l)
log "Backup complete. Total backups retained: $BACKUP_COUNT"

# Optional: Upload to GCS (uncomment if needed)
# if command -v gsutil &> /dev/null; then
#     log "Uploading backup to GCS..."
#     gsutil cp "${BACKUP_DIR}/${BACKUP_FILE}" gs://buddhakorea-backups/redis/
#     log "Upload complete"
# fi

exit 0
