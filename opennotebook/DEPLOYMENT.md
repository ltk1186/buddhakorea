# Buddha Korea RAG System - Production Deployment Guide

Complete guide for deploying Buddha Korea Buddhist AI Chatbot to production.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [VPS Selection & Setup](#vps-selection--setup)
3. [Server Preparation](#server-preparation)
4. [SSL Certificate Setup](#ssl-certificate-setup)
5. [Application Deployment](#application-deployment)
6. [Database Migration](#database-migration)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### Local Requirements
- ✅ ChromaDB database (3.5GB) - **Already created**
- ✅ 99,723 embedded documents - **Already created**
- ✅ API Keys (OpenAI/Anthropic)
- ✅ Domain name (beta.buddhakorea.com)

### Server Requirements
- **CPU**: 2+ vCPUs
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 25GB SSD
- **Bandwidth**: Unlimited or 2TB+
- **OS**: Ubuntu 22.04/24.04 LTS

---

## 2. VPS Selection & Setup

### Recommended Providers

#### Option 1: Hetzner (Best Value) ⭐
```
Server: CPX21
- 3 vCPU AMD
- 4GB RAM
- 80GB SSD
- 20TB traffic
- Cost: €5.83/month (~$6)
- Location: Germany/Finland
```

#### Option 2: DigitalOcean
```
Droplet: Basic
- 2 vCPU
- 4GB RAM
- 80GB SSD
- 4TB traffic
- Cost: $24/month
- Location: Singapore/US
```

#### Option 3: Vultr
```
Cloud Compute: Regular
- 2 vCPU
- 4GB RAM
- 80GB SSD
- 3TB traffic
- Cost: $18/month
- Location: Tokyo/Seoul
```

### VPS Creation Steps

1. **Sign up** for chosen provider
2. **Create server**:
   - OS: Ubuntu 24.04 LTS
   - Region: Closest to Korea (Tokyo/Singapore)
   - SSH key: Upload your public key
   - Hostname: `buddhakorea-beta`

3. **Note down**:
   - IP address (e.g., `123.45.67.89`)
   - Root password (if no SSH key)

---

## 3. Server Preparation

### 3.1 Initial Connection

```bash
# Connect to server
ssh root@YOUR_SERVER_IP

# Update system
apt update && apt upgrade -y

# Set timezone
timedatectl set-timezone Asia/Seoul
```

### 3.2 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version

# Enable Docker on boot
systemctl enable docker
systemctl start docker
```

### 3.3 Create Application User

```bash
# Create non-root user
adduser buddha
usermod -aG sudo,docker buddha

# Switch to buddha user
su - buddha
```

### 3.4 Firewall Setup

```bash
# Install UFW
sudo apt install -y ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Check status
sudo ufw status
```

---

## 4. SSL Certificate Setup

### 4.1 DNS Configuration

**Before continuing**, configure your domain DNS:

```
Type: A Record
Name: beta
Value: YOUR_SERVER_IP
TTL: 3600
```

**Verify DNS propagation**:
```bash
nslookup beta.buddhakorea.com
```

### 4.2 Install Certbot

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Create directory for ACME challenge
sudo mkdir -p /var/www/certbot
```

### 4.3 Obtain SSL Certificate

```bash
# Get certificate
sudo certbot certonly --webroot \
  -w /var/www/certbot \
  -d beta.buddhakorea.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Certificates will be saved to:
# /etc/letsencrypt/live/beta.buddhakorea.com/
```

### 4.4 Auto-renewal Setup

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot auto-renewal is already configured via systemd timer
sudo systemctl status certbot.timer
```

---

## 5. Application Deployment

### 5.1 Upload ChromaDB Database

**On your local machine**:

```bash
# Navigate to project directory
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# Compress ChromaDB (3.5GB -> ~1.5GB compressed)
tar -czf chroma_db.tar.gz chroma_db/

# Upload to server (will take 10-20 minutes)
scp chroma_db.tar.gz buddha@YOUR_SERVER_IP:~/
```

**On the server**:

```bash
# Create application directory
mkdir -p ~/buddhakorea-beta
cd ~/buddhakorea-beta

# Extract ChromaDB
tar -xzf ~/chroma_db.tar.gz
rm ~/chroma_db.tar.gz

# Verify
ls -lh chroma_db/
# Should show chroma.sqlite3 (~3.5GB)
```

### 5.2 Upload Application Files

**On your local machine**:

```bash
# Create deployment package
cd /Users/vairocana/Desktop/buddhakorea/buddha-korea-notebook-exp/opennotebook

# Copy necessary files to a clean directory
mkdir -p deploy_package
cp main.py deploy_package/
cp gemini_query_embedder.py deploy_package/
cp hyde.py deploy_package/
cp reranker.py deploy_package/
cp test_frontend.html deploy_package/
cp requirements.txt deploy_package/
cp docker-compose.yml deploy_package/
cp Dockerfile deploy_package/
cp nginx.conf deploy_package/
cp .dockerignore deploy_package/
cp -r source_explorer deploy_package/

# Create tarball
tar -czf buddha-app.tar.gz deploy_package/

# Upload
scp buddha-app.tar.gz buddha@YOUR_SERVER_IP:~/
```

**On the server**:

```bash
cd ~/buddhakorea-beta

# Extract
tar -xzf ~/buddha-app.tar.gz
mv deploy_package/* .
rmdir deploy_package
rm ~/buddha-app.tar.gz
```

### 5.3 Configure Environment

```bash
# Create .env file
nano .env
```

**Paste this configuration**:

```bash
# LLM API Keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Model Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=BAAI/bge-m3

# ChromaDB
CHROMA_COLLECTION_NAME=cbeta_sutras_gemini

# API Configuration
ALLOWED_ORIGINS=https://buddhakorea.com,https://www.buddhakorea.com,https://beta.buddhakorea.com

# Rate Limiting
RATE_LIMIT_PER_HOUR=100

# Logging
LOG_LEVEL=info

# Retrieval
TOP_K_RETRIEVAL=10
MAX_CONTEXT_TOKENS=8000

# HyDE (optional)
USE_HYDE=false
HYDE_WEIGHT=0.5

# Google Cloud (if using Gemini)
USE_GEMINI_FOR_QUERIES=false
GCP_PROJECT_ID=
GCP_LOCATION=us-central1
```

Save with `Ctrl+O`, exit with `Ctrl+X`.

### 5.4 Setup SSL Certificates for Docker

```bash
# Create SSL directory
mkdir -p ssl

# Copy Let's Encrypt certificates
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/privkey.pem ssl/
sudo chown buddha:buddha ssl/*.pem
sudo chmod 600 ssl/*.pem
```

### 5.5 Create Logs Directory

```bash
mkdir -p logs
```

### 5.6 Build and Start Services

```bash
# Build Docker images (first time only)
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

**Expected output**:
```
NAME                      STATUS    PORTS
buddhakorea-chromadb      Up        0.0.0.0:8001->8000/tcp
buddhakorea-fastapi       Up        0.0.0.0:8000->8000/tcp
buddhakorea-nginx         Up        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

## 6. Database Migration

### 6.1 Verify ChromaDB Connection

```bash
# Check ChromaDB health
curl http://localhost:8001/api/v1/heartbeat

# Should return: {"nanosecond heartbeat": ...}
```

### 6.2 Verify FastAPI Connection

```bash
# Check API health
curl http://localhost:8000/api/health

# Should return:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "chroma_connected": true,
#   "llm_configured": true
# }
```

### 6.3 Test Collections

```bash
# List collections
curl http://localhost:8000/api/collections

# Should return:
# [
#   {
#     "name": "cbeta_sutras_gemini",
#     "document_count": 99723,
#     "language": "multilingual",
#     "description": "..."
#   }
# ]
```

### 6.4 Test Search

```bash
# Test query
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "무상에 대해 설명해주세요",
    "max_sources": 3
  }'
```

---

## 7. Monitoring & Maintenance

### 7.1 View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi
docker compose logs -f chromadb
docker compose logs -f nginx

# FastAPI application logs
tail -f logs/app.log
```

### 7.2 Monitor Resources

```bash
# Install htop
sudo apt install -y htop

# Monitor in real-time
htop

# Docker stats
docker stats
```

### 7.3 Disk Usage

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df
```

### 7.4 Backup ChromaDB

```bash
# Stop services
docker compose stop

# Backup database
tar -czf chroma_db_backup_$(date +%Y%m%d).tar.gz chroma_db/

# Restart services
docker compose start

# Upload backup to remote storage (recommended)
# e.g., rclone, S3, etc.
```

### 7.5 Update Application

```bash
# Pull latest code
cd ~/buddhakorea-beta

# Stop services
docker compose down

# Update files (upload new versions)
# ...

# Rebuild and restart
docker compose build
docker compose up -d

# Check logs
docker compose logs -f
```

---

## 8. Troubleshooting

### 8.1 ChromaDB Not Connecting

```bash
# Check ChromaDB logs
docker compose logs chromadb

# Restart ChromaDB
docker compose restart chromadb

# Verify file permissions
ls -la chroma_db/
```

### 8.2 FastAPI Errors

```bash
# Check FastAPI logs
docker compose logs fastapi

# Check application logs
tail -f logs/app.log

# Restart FastAPI
docker compose restart fastapi

# Check environment variables
docker compose exec fastapi env | grep -E "API_KEY|MODEL"
```

### 8.3 Nginx 502 Bad Gateway

```bash
# Check Nginx logs
docker compose logs nginx

# Check upstream (FastAPI)
docker compose ps fastapi

# Test FastAPI directly
curl http://localhost:8000/api/health

# Restart Nginx
docker compose restart nginx
```

### 8.4 SSL Certificate Issues

```bash
# Check certificate validity
sudo certbot certificates

# Renew manually
sudo certbot renew

# Update Docker SSL files
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/fullchain.pem ~/buddhakorea-beta/ssl/
sudo cp /etc/letsencrypt/live/beta.buddhakorea.com/privkey.pem ~/buddhakorea-beta/ssl/
sudo chown buddha:buddha ~/buddhakorea-beta/ssl/*.pem

# Restart Nginx
cd ~/buddhakorea-beta
docker compose restart nginx
```

### 8.5 High Memory Usage

```bash
# Check memory
free -h

# Check which service is using memory
docker stats

# Restart services
docker compose restart
```

### 8.6 Rate Limiting Issues

```bash
# Check Nginx rate limit logs
docker compose logs nginx | grep "limiting requests"

# Adjust rate limits in nginx.conf
nano nginx.conf

# Reload Nginx
docker compose restart nginx
```

---

## 9. Performance Optimization

### 9.1 Enable Docker Logging Rotation

```bash
# Edit Docker daemon config
sudo nano /etc/docker/daemon.json
```

Add:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Restart Docker
sudo systemctl restart docker
```

### 9.2 Optimize ChromaDB

Already configured in docker-compose.yml:
- Persistent storage
- Health checks
- Resource limits

### 9.3 Add Swap Memory (if needed)

```bash
# Create 4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 10. Cost Summary

### Monthly Costs

| Item | Cost |
|------|------|
| VPS (Hetzner CPX21) | $6/month |
| Domain (already owned) | $0 |
| SSL (Let's Encrypt) | $0 |
| **OpenAI API** | ~$5-20 (usage-based) |
| **Anthropic API** | ~$10-30 (usage-based) |
| **Total** | **$21-56/month** |

### Cost Optimization
- Use Claude 3.5 Sonnet (better quality, similar cost to GPT-4o)
- Enable rate limiting (100/hour already configured)
- Cache common queries (future: Redis)
- Monitor API usage daily

---

## 11. Security Checklist

- ✅ SSL/TLS enabled (Let's Encrypt)
- ✅ Firewall configured (UFW)
- ✅ Non-root user for Docker
- ✅ Rate limiting (Nginx)
- ✅ Security headers (Nginx)
- ✅ Environment variables secured (.env not in git)
- ✅ ChromaDB authentication enabled
- ✅ Docker resource limits
- ✅ Automatic security updates

**Enable unattended upgrades**:
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 12. Going Live

### Pre-Launch Checklist

- [ ] DNS configured and propagated
- [ ] SSL certificate obtained and valid
- [ ] ChromaDB uploaded and verified (99,723 docs)
- [ ] API keys configured
- [ ] All services running and healthy
- [ ] Test queries working
- [ ] Rate limiting tested
- [ ] Logs monitoring working
- [ ] Backup strategy in place
- [ ] Monitoring alerts configured

### Launch Commands

```bash
# Final check
cd ~/buddhakorea-beta
docker compose ps
docker compose logs --tail=50

# If all green, you're live! 🚀
echo "Buddha Korea RAG is now live at https://beta.buddhakorea.com"
```

### Post-Launch

1. **Monitor logs** for first 24 hours
2. **Test from different locations/devices**
3. **Set up uptime monitoring** (e.g., UptimeRobot - free)
4. **Create status page** (optional)
5. **Document known issues**
6. **Plan for scaling** (if traffic grows)

---

## 13. Support

### Useful Commands

```bash
# Quick health check
docker compose ps && curl -s http://localhost:8000/api/health | jq

# Restart everything
docker compose restart

# View real-time logs
docker compose logs -f --tail=100

# Check disk space
df -h && docker system df

# Backup database
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz chroma_db/
```

### Getting Help

- **Docker issues**: `docker compose logs [service]`
- **API errors**: `tail -f logs/app.log`
- **Nginx issues**: `docker compose logs nginx`
- **ChromaDB issues**: Check `chroma_db/chroma.sqlite3` permissions

---

## 14. Next Steps (Future Enhancements)

1. **Monitoring Dashboard** (Grafana + Prometheus)
2. **Redis Caching** (for common queries)
3. **CDN Integration** (CloudFlare)
4. **Auto-scaling** (Kubernetes)
5. **A/B Testing** (different models)
6. **Analytics** (query patterns, popular topics)
7. **Reranking** (MiniLM-L-12)
8. **HyDE** (query expansion)

---

## Congratulations! 🎉

Buddha Korea RAG system is now running in production!

**Access your beta site**: https://beta.buddhakorea.com

**Questions?** Check logs or troubleshooting section above.
