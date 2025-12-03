# Rollback Procedure for Gunicorn Timeout Change

**Date**: 2025-11-22
**Change**: Gunicorn timeout increased from 120s to 300s
**Backup**: `/opt/buddha-korea/Dockerfile.backup-20251122-104329` (on GCP server)
**New Image**: `01dd3030954c`

## When to Rollback

Rollback if you observe:
- Detailed mode queries hanging longer than expected (>5 minutes)
- Increased memory usage or worker issues
- Any unexpected behavior in production

## Rollback Steps

### 1. Restore Original Dockerfile

```bash
cd /opt/buddha-korea
sudo cp Dockerfile.backup-20251122-104329 Dockerfile
```

Verify restoration:
```bash
grep "timeout" Dockerfile
# Should show: "--timeout", "120"
```

### 2. Rebuild Docker Image with Original Configuration

```bash
sudo docker-compose -f docker-compose.production.yml build fastapi
```

This creates a new image with the original 120s timeout.

### 3. Stop and Remove Current Container

```bash
# Find current container ID
sudo docker ps | grep fastapi

# Remove container (replace <container-id> with actual ID)
sudo docker rm -f <container-id>
```

### 4. Start Fresh Container

```bash
sudo docker-compose -f docker-compose.production.yml up -d fastapi
```

### 5. Verify Rollback

```bash
# Check container is running
sudo docker ps | grep fastapi

# Verify Gunicorn timeout is back to 120s
sudo docker exec <container-id> ps aux | grep gunicorn
# Look for: --timeout 120
```

### 6. Test Production Endpoint

```bash
curl -X POST 'https://ai.buddhakorea.com/api/chat' \
  -H 'Content-Type: application/json' \
  -d '{"query":"불교의 사성제는 무엇인가요?","detailed_mode":false}' \
  -w '\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}s\n'
```

Expected: HTTP 200, response in <10 seconds for regular mode.

⚠️ **Note**: After rollback, detailed mode will likely return to showing 502 errors for queries taking >65 seconds.

## Current State (Before Rollback)

- **Dockerfile**: Timeout set to 300s
- **Container**: `17ba0597ac08` (running with 300s timeout)
- **Image**: `01dd3030954c` (buddha-korea_fastapi:latest)
- **Status**: ✅ Working - detailed mode queries completing successfully in ~72s

## Alternative: Partial Rollback (Reduce Timeout)

If 300s seems too long but 120s is too short, you can set an intermediate value:

```dockerfile
"--timeout", "180",  # 3 minutes instead of 5
```

Then rebuild and restart as above.
