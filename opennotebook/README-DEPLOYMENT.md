# Buddha Korea RAG Chatbot - GCP Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Buddha Korea RAG Chatbot to Google Cloud Platform (GCP). The deployment uses Docker containers with file-based ChromaDB and Nginx as a reverse proxy.

**Production Stack:**
- FastAPI backend with Gunicorn + Uvicorn workers
- File-based ChromaDB (3GB, 99,723 documents)
- Gemini embeddings via GCP Vertex AI
- Nginx reverse proxy with SSL
- Docker Compose orchestration

**Migration Path:** GCP → Hetzner (post-demo)

---

## Prerequisites

### Local Machine
- Docker and Docker Compose installed
- `gcloud` CLI configured with your GCP project
- SSH key pair for GCP authentication
- ChromaDB database ready (3.0GB)

### GCP Account
- Active GCP project: `gen-lang-client-0324154376`
- Billing enabled
- Compute Engine API enabled
- Vertex AI API enabled for Gemini embeddings

### API Keys
- OpenAI API key (optional)
- Anthropic API key (optional)
- GCP service account with Vertex AI permissions

---

## Phase 0: Pre-Deployment Verification

### Step 0.1: Verify Local Setup

```bash
# Navigate to project directory
cd /path/to/buddha-korea-notebook-exp/opennotebook

# Verify Docker is running
docker --version
docker compose version

# Verify ChromaDB exists and size
du -sh chroma_db/
# Expected: ~3.0GB

# Check ChromaDB structure
ls -lh chroma_db/5583454a-9473-4ec8-bcb7-6412c95c27ed/
# Should see chroma.sqlite3 (~1.8GB)

# Verify local server runs
source ../../venv/bin/activate
python main.py
# Wait for "Buddhist AI Chatbot ready!" message
# Ctrl+C to stop
```

### Step 0.2: Verify Required Files

```bash
# Check all deployment files exist
ls -la | grep -E "(Dockerfile|docker-compose|nginx.conf|requirements.txt|\.env)"

# Verify production files created
ls -la .env.production docker-compose.production.yml .dockerignore
```

**Expected files:**
- ✅ `Dockerfile` - Multi-stage production build
- ✅ `docker-compose.production.yml` - GCP production compose file
- ✅ `nginx.conf` - Reverse proxy configuration
- ✅ `requirements.txt` - Python dependencies
- ✅ `.env.production` - Production environment template
- ✅ `.dockerignore` - Docker build optimization

---

## Phase 1: File Preparation (COMPLETED ✅)

The following files have been prepared and are ready for deployment:

### 1.1 `.env.production` Template
Production environment configuration with placeholders for API keys.

**Before deployment, update:**
- `OPENAI_API_KEY` - Add your OpenAI API key
- `ANTHROPIC_API_KEY` - Add your Anthropic API key
- `ALLOWED_ORIGINS` - Update with your actual domain(s)

### 1.2 `docker-compose.production.yml`
Simplified Docker Compose configuration for GCP using file-based ChromaDB.

**Key features:**
- Single FastAPI container with ChromaDB volume mount
- Nginx reverse proxy with SSL support
- Health checks and resource limits
- Read-only ChromaDB mount for data safety

### 1.3 `.dockerignore`
Optimized Docker build by excluding unnecessary files.

**Excludes:** test files, virtual environments, documentation, logs, git files, local development artifacts

---

## Phase 2: GCP VM Creation

### Step 2.1: Create Compute Engine VM

```bash
# Set project ID
gcloud config set project gen-lang-client-0324154376

# Create VM instance (recommended specs for RAG chatbot)
gcloud compute instances create buddhakorea-rag-server \
  --zone=us-central1-a \
  --machine-type=e2-standard-4 \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-balanced \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=http-server,https-server \
  --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y docker.io docker-compose curl git
systemctl enable docker
systemctl start docker
usermod -aG docker $USER'
```

**Machine specifications:**
- **Type:** e2-standard-4 (4 vCPUs, 16GB RAM)
- **Disk:** 50GB SSD (pd-balanced)
- **OS:** Ubuntu 22.04 LTS
- **Region:** us-central1-a (same as Vertex AI)

**Why these specs?**
- 16GB RAM: ChromaDB (3GB) + FastAPI + Docker overhead
- 50GB disk: ChromaDB (3GB) + Docker images (~5GB) + logs + buffer
- Same region as Vertex AI: Lower latency for Gemini embeddings

### Step 2.2: Configure Firewall Rules

```bash
# Allow HTTP traffic
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 \
  --target-tags http-server \
  --description "Allow HTTP traffic"

# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https \
  --allow tcp:443 \
  --target-tags https-server \
  --description "Allow HTTPS traffic"

# Verify firewall rules
gcloud compute firewall-rules list --filter="name~(allow-http|allow-https)"
```

### Step 2.3: Get VM External IP

```bash
# Get external IP address
gcloud compute instances describe buddhakorea-rag-server \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# Save this IP for DNS configuration later
```

---

## Phase 3: Server Initial Setup

### Step 3.1: SSH into Server

```bash
# SSH into the VM
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a

# Verify Docker installation
docker --version
docker compose version

# Create application directory
mkdir -p ~/buddhakorea-app
cd ~/buddhakorea-app
```

### Step 3.2: Install Additional Tools

```bash
# Install required tools
sudo apt-get update
sudo apt-get install -y \
  curl \
  git \
  vim \
  htop \
  ufw \
  certbot \
  python3-certbot-nginx

# Verify installations
curl --version
git --version
certbot --version
```

### Step 3.3: Configure Application User

```bash
# Ensure current user is in docker group
sudo usermod -aG docker $USER

# Apply group membership (or log out and back in)
newgrp docker

# Verify docker access without sudo
docker ps
```

---

## Phase 4: File Upload

### Step 4.1: Prepare ChromaDB for Upload (Local Machine)

```bash
# On local machine
cd /path/to/buddha-korea-notebook-exp/opennotebook

# Compress ChromaDB directory
tar -czf chroma_db.tar.gz chroma_db/

# Verify compressed size
ls -lh chroma_db.tar.gz
# Expected: ~800MB-1.2GB compressed
```

### Step 4.2: Upload Application Files

```bash
# Upload main application files
gcloud compute scp --zone=us-central1-a \
  --recurse \
  main.py \
  Dockerfile \
  docker-compose.production.yml \
  nginx.conf \
  requirements.txt \
  .dockerignore \
  buddhakorea-rag-server:~/buddhakorea-app/

# Upload static files (if any)
gcloud compute scp --zone=us-central1-a \
  --recurse \
  static/ \
  buddhakorea-rag-server:~/buddhakorea-app/

# Upload source explorer (if needed)
gcloud compute scp --zone=us-central1-a \
  --recurse \
  source_explorer/ \
  buddhakorea-rag-server:~/buddhakorea-app/
```

### Step 4.3: Upload ChromaDB

```bash
# Upload compressed ChromaDB (this may take 10-30 minutes)
gcloud compute scp --zone=us-central1-a \
  chroma_db.tar.gz \
  buddhakorea-rag-server:~/buddhakorea-app/

# SSH into server
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a

# Extract ChromaDB
cd ~/buddhakorea-app
tar -xzf chroma_db.tar.gz

# Verify extraction
du -sh chroma_db/
ls -lh chroma_db/5583454a-9473-4ec8-bcb7-6412c95c27ed/

# Clean up compressed file
rm chroma_db.tar.gz

# Set proper permissions
chmod -R 755 chroma_db/
```

### Step 4.4: Configure Environment Variables

```bash
# SSH into server (if not already)
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a
cd ~/buddhakorea-app

# Copy production template to .env
cp .env.production .env

# Edit .env with your actual API keys
nano .env

# Update these values:
# - OPENAI_API_KEY=your-actual-openai-key
# - ANTHROPIC_API_KEY=your-actual-anthropic-key
# - ALLOWED_ORIGINS=https://buddhakorea.com,https://www.buddhakorea.com

# Verify .env file
grep -E "^(OPENAI|ANTHROPIC|ALLOWED_ORIGINS)" .env
```

**IMPORTANT:** Never commit `.env` with actual API keys to version control!

---

## Phase 5: Docker Deployment

### Step 5.1: Rename Docker Compose File

```bash
# SSH into server
cd ~/buddhakorea-app

# Rename production compose file
mv docker-compose.production.yml docker-compose.yml

# Verify file structure
ls -la
```

### Step 5.2: Build Docker Image

```bash
# Build the Docker image (takes 5-10 minutes)
docker compose build --no-cache

# Verify image built successfully
docker images | grep buddhakorea
```

### Step 5.3: Start Services

```bash
# Start all services in detached mode
docker compose up -d

# Verify containers are running
docker compose ps

# Expected output:
# NAME                     STATUS
# buddhakorea-fastapi      Up (healthy)
# buddhakorea-nginx        Up
```

### Step 5.4: Check Logs

```bash
# View FastAPI logs
docker compose logs -f fastapi

# Wait for startup messages:
# - "Starting Buddhist AI Chatbot..."
# - "✓ Embeddings loaded"
# - "✓ Connected to ChromaDB"
# - "Documents: 99,723"
# - "✓ LLM initialized"
# - "🚀 Buddhist AI Chatbot ready!"

# Press Ctrl+C to exit logs

# View Nginx logs
docker compose logs nginx
```

### Step 5.5: Test Health Endpoint

```bash
# Test health endpoint (should return OK)
curl http://localhost:8000/api/health

# Test API directly
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"무상이란 무엇인가요?","detailed_mode":false}'
```

---

## Phase 6: Domain Connection

### Step 6.1: Configure DNS (Your Domain Registrar)

Point your domain to the GCP VM's external IP address:

```
Type: A Record
Name: @ (or buddhakorea.com)
Value: <YOUR_VM_EXTERNAL_IP>
TTL: 300 (or default)

Type: A Record
Name: www
Value: <YOUR_VM_EXTERNAL_IP>
TTL: 300 (or default)
```

### Step 6.2: Verify DNS Propagation

```bash
# Check DNS resolution (on local machine)
dig buddhakorea.com +short
dig www.buddhakorea.com +short

# Both should return your VM's IP address

# Alternative check
nslookup buddhakorea.com
```

**Note:** DNS propagation can take 5 minutes to 48 hours depending on TTL and registrar.

---

## Phase 7: SSL Setup with Let's Encrypt

### Step 7.1: Stop Nginx (Temporarily)

```bash
# SSH into server
cd ~/buddhakorea-app

# Stop nginx container temporarily for certbot standalone mode
docker compose stop nginx
```

### Step 7.2: Obtain SSL Certificate

```bash
# Run certbot in standalone mode
sudo certbot certonly --standalone \
  -d buddhakorea.com \
  -d www.buddhakorea.com \
  --agree-tos \
  --email your-email@example.com \
  --non-interactive

# Verify certificates created
sudo ls -la /etc/letsencrypt/live/buddhakorea.com/

# Expected files:
# - cert.pem
# - chain.pem
# - fullchain.pem
# - privkey.pem
```

### Step 7.3: Copy Certificates to Docker Volume

```bash
# Create SSL directory for Docker mount
mkdir -p ~/buddhakorea-app/ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/buddhakorea.com/fullchain.pem \
  ~/buddhakorea-app/ssl/
sudo cp /etc/letsencrypt/live/buddhakorea.com/privkey.pem \
  ~/buddhakorea-app/ssl/

# Set proper permissions
sudo chown $USER:$USER ~/buddhakorea-app/ssl/*
chmod 644 ~/buddhakorea-app/ssl/fullchain.pem
chmod 600 ~/buddhakorea-app/ssl/privkey.pem
```

### Step 7.4: Update Nginx Configuration

```bash
# Edit nginx.conf to enable SSL
nano ~/buddhakorea-app/nginx.conf

# Ensure SSL configuration is present and uncommented:
# - listen 443 ssl http2;
# - ssl_certificate /etc/nginx/ssl/fullchain.pem;
# - ssl_certificate_key /etc/nginx/ssl/privkey.pem;
# - HTTP to HTTPS redirect on port 80
```

### Step 7.5: Restart Services

```bash
# Restart all services with SSL
docker compose down
docker compose up -d

# Verify services are running
docker compose ps

# Check nginx logs for SSL errors
docker compose logs nginx | grep -i ssl
```

### Step 7.6: Setup Auto-Renewal

```bash
# Test renewal process
sudo certbot renew --dry-run

# Create renewal script
sudo nano /etc/cron.weekly/certbot-renew

# Add this content:
#!/bin/bash
certbot renew --quiet --deploy-hook "cd /home/$USER/buddhakorea-app && docker compose restart nginx"

# Make executable
sudo chmod +x /etc/cron.weekly/certbot-renew
```

---

## Phase 8: Final Testing and Verification

### Step 8.1: Test HTTPS Access

```bash
# Test from local machine
curl https://buddhakorea.com/api/health

# Should return: {"status":"ok"}

# Test in browser
# Navigate to: https://buddhakorea.com
# Verify SSL certificate is valid (green padlock)
```

### Step 8.2: Test RAG Chat API

```bash
# Test basic query
curl -X POST https://buddhakorea.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "무상(無常)의 의미는?",
    "detailed_mode": false
  }'

# Test detailed mode
curl -X POST https://buddhakorea.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "사성제에 대해 자세히 설명해주세요",
    "detailed_mode": true
  }'

# Verify response includes:
# - "response": <LLM response>
# - "sources": [array of source texts]
# - "session_id": <UUID>
```

### Step 8.3: Test Source Explorer API

```bash
# Get source list
curl https://buddhakorea.com/api/sources?limit=10

# Get specific source
curl https://buddhakorea.com/api/sources/T01n0001

# Verify returns sutra metadata and content
```

### Step 8.4: Monitor Performance

```bash
# SSH into server
gcloud compute ssh buddhakorea-rag-server --zone=us-central1-a

# Check container stats
docker stats

# Check memory usage
free -h

# Check disk usage
df -h

# Check ChromaDB size
du -sh ~/buddhakorea-app/chroma_db/

# View real-time logs
docker compose logs -f --tail=50
```

### Step 8.5: Load Testing (Optional)

```bash
# Install Apache Bench (on local machine)
sudo apt-get install apache2-utils  # Ubuntu/Debian
brew install ab  # macOS

# Run simple load test (100 requests, 10 concurrent)
ab -n 100 -c 10 \
  -H "Content-Type: application/json" \
  -p query.json \
  https://buddhakorea.com/api/chat

# Create query.json first:
echo '{"query":"무상이란 무엇인가요?","detailed_mode":false}' > query.json
```

---

## Troubleshooting

### Issue: Container Won't Start

```bash
# Check logs
docker compose logs fastapi

# Common issues:
# 1. ChromaDB not found → verify chroma_db/ directory exists
# 2. API keys missing → check .env file
# 3. Port conflict → check if port 8000 is already in use

# Restart services
docker compose down
docker compose up -d
```

### Issue: Health Check Failing

```bash
# Check if FastAPI is running
curl http://localhost:8000/api/health

# Check container health status
docker compose ps

# View detailed logs
docker compose logs fastapi | tail -100

# Restart unhealthy container
docker compose restart fastapi
```

### Issue: Nginx 502 Bad Gateway

```bash
# Check FastAPI is responding
docker exec -it buddhakorea-fastapi curl http://localhost:8000/api/health

# Check Nginx can reach FastAPI
docker compose logs nginx | grep upstream

# Verify network connectivity
docker compose exec nginx ping -c 3 fastapi

# Restart services
docker compose restart
```

### Issue: SSL Certificate Errors

```bash
# Verify certificate files exist
sudo ls -la /etc/letsencrypt/live/buddhakorea.com/

# Check certificate expiration
sudo certbot certificates

# Renew certificate manually
sudo certbot renew --force-renewal

# Restart nginx
docker compose restart nginx
```

### Issue: ChromaDB Connection Failed

```bash
# Verify ChromaDB files exist
ls -la ~/buddhakorea-app/chroma_db/

# Check ChromaDB collection
docker compose exec fastapi python -c "
from chromadb import PersistentClient
client = PersistentClient(path='./chroma_db')
print(client.list_collections())
"

# Verify document count
docker compose exec fastapi python -c "
from chromadb import PersistentClient
client = PersistentClient(path='./chroma_db')
coll = client.get_collection('cbeta_sutras_gemini')
print(f'Documents: {coll.count():,}')
"
```

### Issue: High Memory Usage

```bash
# Check memory usage
docker stats --no-stream

# Reduce resource limits in docker-compose.yml
nano docker-compose.yml
# Update: memory: 3G (instead of 4G)

# Restart with new limits
docker compose down
docker compose up -d
```

### Issue: Slow Response Times

```bash
# Check Gemini API latency
docker compose exec fastapi python -c "
import time
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel
model = TextEmbeddingModel.from_pretrained('text-embedding-004')
start = time.time()
model.get_embeddings([TextEmbeddingInput('test', 'RETRIEVAL_QUERY')])
print(f'Embedding latency: {(time.time()-start)*1000:.0f}ms')
"

# Check ChromaDB query performance
docker compose exec fastapi python -c "
import time
from chromadb import PersistentClient
client = PersistentClient(path='./chroma_db')
coll = client.get_collection('cbeta_sutras_gemini')
start = time.time()
coll.query(query_texts=['무상'], n_results=10)
print(f'ChromaDB query: {(time.time()-start)*1000:.0f}ms')
"
```

---

## Monitoring and Maintenance

### Daily Checks

```bash
# Check service status
docker compose ps

# Check disk space
df -h

# Check latest logs
docker compose logs --tail=50 fastapi
```

### Weekly Maintenance

```bash
# Check for Docker image updates
docker compose pull

# Prune unused Docker resources
docker system prune -a --volumes

# Backup ChromaDB (if modified)
tar -czf chroma_db_backup_$(date +%Y%m%d).tar.gz chroma_db/
```

### Monthly Tasks

```bash
# Review and archive logs
docker compose logs fastapi > logs/fastapi_$(date +%Y%m).log

# Check SSL certificate expiration
sudo certbot certificates

# Review resource usage trends
docker stats --no-stream > stats_$(date +%Y%m%d).txt
```

---

## Scaling Considerations

### Vertical Scaling (Current Setup)

If you need more resources:

```bash
# Stop instance
gcloud compute instances stop buddhakorea-rag-server --zone=us-central1-a

# Change machine type
gcloud compute instances set-machine-type buddhakorea-rag-server \
  --zone=us-central1-a \
  --machine-type=e2-standard-8

# Start instance
gcloud compute instances start buddhakorea-rag-server --zone=us-central1-a
```

### Horizontal Scaling (Future)

For high traffic, consider:
- Load balancer with multiple FastAPI instances
- Managed ChromaDB service or read replicas
- Caching layer (Redis) for frequent queries
- CDN for static assets

---

## Migration to Hetzner (Post-Demo)

After GCP demonstration, follow these steps to migrate to Hetzner:

### Step 1: Prepare Hetzner Server

```bash
# Create Hetzner Cloud Server via web UI:
# - Type: CX31 (4 vCPUs, 16GB RAM)
# - Location: Nuremberg, Germany (eu-central)
# - Image: Ubuntu 22.04
# - SSH key: Add your public key

# SSH into Hetzner server
ssh root@<HETZNER_IP>

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### Step 2: Transfer Files from GCP

```bash
# On GCP server, create backup
cd ~/buddhakorea-app
tar -czf buddhakorea-backup.tar.gz \
  --exclude='logs' \
  --exclude='*.log' \
  .

# Transfer directly GCP → Hetzner
scp ~/buddhakorea-app/buddhakorea-backup.tar.gz \
  root@<HETZNER_IP>:/root/

# On Hetzner server, extract
cd /root
tar -xzf buddhakorea-backup.tar.gz -C /opt/buddhakorea/
```

### Step 3: Update DNS

Update DNS A records to point to Hetzner IP:
- buddhakorea.com → `<HETZNER_IP>`
- www.buddhakorea.com → `<HETZNER_IP>`

### Step 4: Obtain New SSL Certificate

```bash
# On Hetzner server
certbot certonly --standalone \
  -d buddhakorea.com \
  -d www.buddhakorea.com

# Copy certificates to Docker volume
cp /etc/letsencrypt/live/buddhakorea.com/*.pem /opt/buddhakorea/ssl/
```

### Step 5: Deploy on Hetzner

```bash
# Start services
cd /opt/buddhakorea
docker compose up -d

# Verify
curl https://buddhakorea.com/api/health
```

### Step 6: Decommission GCP

```bash
# Stop GCP instance
gcloud compute instances stop buddhakorea-rag-server --zone=us-central1-a

# After confirming Hetzner is stable, delete GCP instance
gcloud compute instances delete buddhakorea-rag-server --zone=us-central1-a
```

---

## Security Best Practices

### 1. API Key Management
- Never commit `.env` with real API keys to Git
- Rotate API keys every 90 days
- Use environment-specific keys (dev, staging, prod)

### 2. Server Hardening
```bash
# Enable firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Disable password authentication (SSH keys only)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd

# Keep system updated
sudo apt-get update && sudo apt-get upgrade -y
```

### 3. Docker Security
```bash
# Run containers as non-root (already configured in Dockerfile)
# Use read-only ChromaDB mount (already configured)
# Regular security updates
docker compose pull
docker compose up -d
```

### 4. Monitoring
```bash
# Install monitoring tools
sudo apt-get install fail2ban

# Configure fail2ban for SSH
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## Cost Estimation

### GCP (Monthly)

| Resource | Specification | Cost (USD) |
|----------|--------------|------------|
| e2-standard-4 VM | 4 vCPUs, 16GB RAM | ~$120 |
| 50GB SSD | pd-balanced | ~$8 |
| Network egress | ~500GB | ~$50 |
| Vertex AI (Gemini) | Embeddings + LLM | ~$50-200 |
| **Total** | | **~$228-378/month** |

### Hetzner (Monthly)

| Resource | Specification | Cost (EUR) |
|----------|--------------|------------|
| CX31 Server | 4 vCPUs, 16GB RAM | €11.00 |
| Network | 20TB included | €0 |
| **Total** | | **~€11/month (~$12)** |

**Savings:** ~95% cost reduction by migrating to Hetzner

**Note:** Hetzner does not provide Vertex AI, so you'll need to:
- Use OpenAI embeddings instead (`text-embedding-3-large`)
- Update environment variables in `.env`
- Additional cost: ~$20-50/month for OpenAI API

---

## Support and Resources

### Documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [GCP Compute Engine](https://cloud.google.com/compute/docs)

### Monitoring Dashboards
- GCP Console: https://console.cloud.google.com/
- Docker health: `docker compose ps`
- Application logs: `docker compose logs -f`

### Emergency Contacts
- GCP Support: https://cloud.google.com/support
- Docker Support: https://forums.docker.com/

---

## Appendix: File Checklist

**Files on GCP Server (`~/buddhakorea-app/`):**

```
.
├── .dockerignore
├── .env (from .env.production template, with actual API keys)
├── docker-compose.yml (renamed from docker-compose.production.yml)
├── Dockerfile
├── main.py
├── nginx.conf
├── requirements.txt
├── chroma_db/ (3.0GB extracted from tar.gz)
│   └── 5583454a-9473-4ec8-bcb7-6412c95c27ed/
│       └── chroma.sqlite3
├── ssl/
│   ├── fullchain.pem
│   └── privkey.pem
├── static/ (optional)
└── source_explorer/ (optional)
```

**Deployment Status Checklist:**

- [ ] Phase 0: Local verification completed
- [ ] Phase 1: Deployment files prepared
- [ ] Phase 2: GCP VM created
- [ ] Phase 3: Server initial setup completed
- [ ] Phase 4: Files uploaded (including ChromaDB)
- [ ] Phase 5: Docker services running
- [ ] Phase 6: Domain DNS configured
- [ ] Phase 7: SSL certificate installed
- [ ] Phase 8: Production testing passed

---

**Document Version:** 1.0
**Last Updated:** 2025-11-21
**Prepared By:** Claude Code
**Project:** Buddha Korea RAG Chatbot
**Target Environment:** Google Cloud Platform (GCP) → Hetzner
