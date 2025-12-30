# Secrets Management Guide

This document explains how secrets are managed, deployed, and rotated in the Buddha Korea project.

## Overview

Secrets flow from **GitHub Actions Secrets** → **Hetzner Server** during deployment. The GitHub Actions workflow (`deploy-hetzner.yml`) reads secrets and applies them to the server environment.

**Flow:**
1. Secrets stored securely in GitHub repository settings
2. Workflow accesses secrets via `${{ secrets.SECRET_NAME }}`
3. Deployment script generates `.env` file on server
4. Docker Compose reads `.env` to configure containers
5. Special handling for GCP service account and PostgreSQL password

## GitHub Secrets Inventory

All 16 secrets currently configured:

| Secret Name | Purpose | Used By |
|-------------|---------|---------|
| `HETZNER_HOST` | Server IP address (157.180.72.0) | SSH connection |
| `HETZNER_USERNAME` | SSH username (root) | SSH connection |
| `HETZNER_SSH_KEY` | SSH private key for authentication | SSH connection |
| `SECRET_KEY` | FastAPI session encryption key | Backend app |
| `REDIS_PASSWORD` | Redis authentication password | Redis + Backend |
| `POSTGRES_PASSWORD` | PostgreSQL database password | PostgreSQL + Backend |
| `GEMINI_API_KEY` | Main Gemini AI API key | AI features |
| `PALI_GEMINI_API_KEY` | Pali Studio specific Gemini key | Pali-specific AI |
| `GCP_PROJECT_ID` | Google Cloud Platform project ID | GCP services |
| `GCP_SERVICE_ACCOUNT_KEY` | Full JSON service account key | GCP authentication |
| `GOOGLE_CLIENT_ID` | OAuth - Google login | Authentication |
| `GOOGLE_CLIENT_SECRET` | OAuth - Google login | Authentication |
| `NAVER_CLIENT_ID` | OAuth - Naver login | Authentication |
| `NAVER_CLIENT_SECRET` | OAuth - Naver login | Authentication |
| `KAKAO_CLIENT_ID` | OAuth - Kakao login | Authentication |
| `KAKAO_CLIENT_SECRET` | OAuth - Kakao login | Authentication |

## How Secrets Are Applied

### 1. Environment File Generation

During deployment, the workflow generates `/root/buddhakorea/.env`:

```bash
echo "SECRET_KEY=${SECRET_KEY}" > .env
echo "REDIS_PASSWORD=${REDIS_PASSWORD}" >> .env
echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" >> .env
# ... all other secrets
```

Docker Compose reads this file to inject environment variables into containers.

### 2. GCP Service Account Key

The `GCP_SERVICE_ACCOUNT_KEY` secret contains the **full JSON content** of the service account key file:

```bash
echo "${GCP_SERVICE_ACCOUNT_KEY}" > /root/buddhakorea/gcp-key.json
```

This file is mounted into containers that need GCP access (e.g., Cloud Storage, Vertex AI).

### 3. PostgreSQL Password Synchronization

After containers start, the workflow syncs the PostgreSQL password:

```bash
docker exec buddhakorea-postgres psql -U postgres -c \
  "ALTER USER postgres WITH PASSWORD '${POSTGRES_PASSWORD}';"
```

This ensures the running PostgreSQL instance uses the password from GitHub Secrets.

## Rotating Secrets

### Standard Secret Rotation

For most secrets (API keys, OAuth credentials, session keys):

1. **Generate new secret value**
   - Use a secure random generator
   - For API keys: regenerate in provider console (Google Cloud, Naver, Kakao)

2. **Update GitHub Secret**
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Click on secret name
   - Update value and save

3. **Trigger deployment**
   - Push to `main` branch (automatic), OR
   - Go to Actions → "Deploy to Hetzner" → Run workflow (manual)

4. **Verify service**
   - Check application logs: `docker logs buddhakorea-backend`
   - Test affected functionality (login, AI features, etc.)

### PostgreSQL Password Rotation

Special procedure required:

1. Update `POSTGRES_PASSWORD` in GitHub Secrets
2. Deploy (password sync happens automatically via `ALTER USER` command)
3. Verify: `docker exec buddhakorea-postgres psql -U postgres -c "\du"`

### GCP Service Account Key Rotation

1. In Google Cloud Console, create new service account key
2. Download JSON file
3. Copy **entire JSON content** to `GCP_SERVICE_ACCOUNT_KEY` secret
4. Deploy (new `gcp-key.json` will be written)
5. Delete old key from Google Cloud Console

### SSH Key Rotation

1. Generate new SSH key pair: `ssh-keygen -t ed25519`
2. Add public key to server: `/root/.ssh/authorized_keys`
3. Update `HETZNER_SSH_KEY` secret with new private key
4. Test deployment workflow
5. Remove old public key from server

## Security Best Practices

1. **Never commit secrets** - All sensitive values must be in GitHub Secrets
2. **Rotate regularly** - Especially API keys and passwords (quarterly recommended)
3. **Use least privilege** - GCP service account should have minimal required permissions
4. **Monitor access** - Review GitHub Actions logs for unauthorized deployments
5. **Separate environments** - Use different secrets for production vs. staging
6. **Audit trail** - GitHub maintains history of secret updates (not values, only timestamps)

## Troubleshooting

**Deployment fails with authentication error:**
- Check `HETZNER_SSH_KEY` is correctly formatted (include `-----BEGIN` and `-----END` lines)
- Verify `HETZNER_HOST` and `HETZNER_USERNAME` are correct

**Application can't connect to database:**
- Check `POSTGRES_PASSWORD` matches in `.env` and PostgreSQL
- Verify password sync step completed in workflow logs

**GCP services failing:**
- Verify `GCP_SERVICE_ACCOUNT_KEY` contains valid JSON
- Check service account has required roles in GCP Console
- Ensure `gcp-key.json` exists in container: `docker exec buddhakorea-backend ls -l /app/gcp-key.json`

**OAuth login not working:**
- Verify redirect URIs match in provider console (Google/Naver/Kakao)
- Check client ID and secret are correct
- Ensure `SECRET_KEY` hasn't changed (would invalidate sessions)

## Emergency Access

If GitHub Actions is unavailable, secrets can be manually applied:

1. SSH to server: `ssh root@157.180.72.0`
2. Edit `.env` file: `nano /root/buddhakorea/.env`
3. Restart containers: `docker-compose restart`

**Warning:** Manual changes will be overwritten on next deployment.
