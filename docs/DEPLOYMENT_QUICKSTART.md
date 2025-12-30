# Buddha Korea - Deployment Quick Start

**Last Updated:** 2025-12-30

This guide provides actionable steps for deploying Buddha Korea to production.

---

## Prerequisites Checklist

### Required GitHub Secrets (13 total)

Configure these in: **GitHub Repository → Settings → Secrets and variables → Actions**

#### Server Access (3 secrets)
- [ ] `HETZNER_HOST` - Server IP: `157.180.72.0`
- [ ] `HETZNER_USERNAME` - SSH username
- [ ] `HETZNER_SSH_KEY` - Private SSH key for authentication

#### Application Secrets (2 secrets)
- [ ] `SECRET_KEY` - Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] `REDIS_PASSWORD` - Redis authentication password

#### Database (1 secret)
- [ ] `POSTGRES_PASSWORD` - PostgreSQL password (workflow auto-syncs with ALTER USER)

#### Google Cloud Platform (3 secrets)
- [ ] `GEMINI_API_KEY` - Gemini API key for general use
- [ ] `PALI_GEMINI_API_KEY` - Gemini API key for Pali Canon
- [ ] `GCP_PROJECT_ID` - Google Cloud project ID
- [ ] `GCP_SERVICE_ACCOUNT_KEY` - Service account JSON key (workflow auto-generates credentials.json)

#### OAuth Providers (6 secrets)
- [ ] `GOOGLE_CLIENT_ID` - Google OAuth client ID
- [ ] `GOOGLE_CLIENT_SECRET` - Google OAuth client secret
- [ ] `NAVER_CLIENT_ID` - Naver OAuth client ID
- [ ] `NAVER_CLIENT_SECRET` - Naver OAuth client secret
- [ ] `KAKAO_CLIENT_ID` - Kakao OAuth client ID (REST API key)
- [ ] `KAKAO_CLIENT_SECRET` - Kakao OAuth client secret

---

## One-Command Deployment (GitHub Actions)

### Automatic Deployment

Pushes to `main` branch automatically deploy if changes affect:
- `backend/**`
- `config/**`
- `Dockerfile`
- `.github/workflows/deploy.yml`

**Workflow:** `.github/workflows/deploy.yml`

### Manual Deployment

Trigger deployment manually via GitHub UI:

1. Go to **Actions** tab in GitHub repository
2. Select **Deploy to Hetzner** workflow
3. Click **Run workflow** dropdown
4. Select `main` branch
5. Click **Run workflow** button

**Health Check:** https://ai.buddhakorea.com/api/health

---

## Manual Deployment (SSH)

### Quick Commands

```bash
# SSH into production server
ssh prod
# Or: ssh <username>@157.180.72.0

# Navigate to project directory
cd /opt/buddha-korea

# Pull latest code
git pull origin main

# Rebuild and restart containers
docker compose -f config/docker-compose.yml down
docker compose -f config/docker-compose.yml up -d --build

# View logs
docker compose -f config/docker-compose.yml logs -f
```

### Container Management

```bash
# View running containers (4 expected)
docker compose -f config/docker-compose.yml ps

# Expected containers:
# - buddhakorea-backend
# - buddhakorea-nginx
# - buddhakorea-redis
# - buddhakorea-postgres

# Restart specific service
docker compose -f config/docker-compose.yml restart backend

# View logs for specific service
docker compose -f config/docker-compose.yml logs -f backend

# Execute commands in backend container
docker compose -f config/docker-compose.yml exec backend python manage.py migrate
docker compose -f config/docker-compose.yml exec backend python manage.py collectstatic --noinput
```

### Environment File Updates

```bash
# Edit .env file on server
cd /opt/buddha-korea
nano .env

# After editing, restart affected services
docker compose -f config/docker-compose.yml restart backend
```

---

## Troubleshooting Common Issues

### 502 Bad Gateway

**Cause:** Backend container not healthy or not responding

**Solution:**
```bash
# Check backend container status
docker compose -f config/docker-compose.yml ps backend

# View backend logs
docker compose -f config/docker-compose.yml logs -f backend

# Restart backend
docker compose -f config/docker-compose.yml restart backend

# If still failing, rebuild
docker compose -f config/docker-compose.yml up -d --build backend
```

### PostgreSQL Authentication Failed

**Cause:** Password mismatch between .env and database user

**Solution (Automatic):**
The workflow now automatically syncs passwords using:
```sql
ALTER USER postgres WITH PASSWORD '<new-password>';
```

**Solution (Manual):**
```bash
# Connect to PostgreSQL container
docker compose -f config/docker-compose.yml exec postgres psql -U postgres

# Update password
ALTER USER postgres WITH PASSWORD 'your-new-password';
\q

# Update .env file to match
nano .env  # Update POSTGRES_PASSWORD

# Restart backend
docker compose -f config/docker-compose.yml restart backend
```

### GCP 401 Unauthenticated

**Cause:** Invalid or missing GCP service account key

**Solution:**
```bash
# Verify credentials.json exists on server
ls -la /opt/buddha-korea/backend/credentials.json

# Check file permissions
chmod 600 /opt/buddha-korea/backend/credentials.json

# Verify GCP_SERVICE_ACCOUNT_KEY secret in GitHub
# Re-run deployment to regenerate credentials.json
```

### nginx Container Not Starting

**Cause:** Missing or invalid SSL certificates

**Solution:**
```bash
# Check SSL certificate files
ls -la /opt/buddha-korea/config/ssl/

# Expected files:
# - fullchain.pem
# - privkey.pem

# Check nginx configuration
docker compose -f config/docker-compose.yml exec nginx nginx -t

# View nginx logs
docker compose -f config/docker-compose.yml logs nginx
```

### Redis Connection Failed

**Cause:** Redis password mismatch or service not running

**Solution:**
```bash
# Check Redis container status
docker compose -f config/docker-compose.yml ps redis

# Test Redis connection
docker compose -f config/docker-compose.yml exec redis redis-cli -a <REDIS_PASSWORD> ping
# Expected: PONG

# Restart Redis
docker compose -f config/docker-compose.yml restart redis
```

---

## Verification Steps

After deployment, verify all services:

```bash
# 1. Check all containers are running
docker compose -f config/docker-compose.yml ps
# All should show "Up" status

# 2. Check health endpoint
curl https://ai.buddhakorea.com/api/health
# Expected: {"status": "healthy"}

# 3. Check backend logs for errors
docker compose -f config/docker-compose.yml logs backend | grep -i error

# 4. Test static file serving
curl -I https://ai.buddhakorea.com/static/admin/css/base.css
# Expected: HTTP/1.1 200 OK
```

---

## Rollback Procedure

If deployment fails:

```bash
# 1. View recent commits
cd /opt/buddha-korea
git log --oneline -5

# 2. Rollback to previous commit
git reset --hard <previous-commit-hash>

# 3. Rebuild containers
docker compose -f config/docker-compose.yml down
docker compose -f config/docker-compose.yml up -d --build

# 4. Verify health
curl https://ai.buddhakorea.com/api/health
```

---

## Quick Reference

| Resource | Location |
|----------|----------|
| Server IP | 157.180.72.0 |
| SSH Alias | `ssh prod` |
| Project Path | `/opt/buddha-korea` |
| Docker Compose | `config/docker-compose.yml` |
| Environment File | `/opt/buddha-korea/.env` |
| Health Check | https://ai.buddhakorea.com/api/health |
| GitHub Workflow | `.github/workflows/deploy.yml` |

---

## Support

For additional help:
1. Check GitHub Actions logs for deployment errors
2. Review container logs: `docker compose -f config/docker-compose.yml logs -f`
3. Verify all GitHub Secrets are configured correctly
4. Ensure .env file on server matches required variables
