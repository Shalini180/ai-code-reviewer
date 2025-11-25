# AI Code Reviewer - Deployment Guide

## Overview

The AI Code Reviewer is a hybrid analysis system that combines static analysis tools (Semgrep, Bandit) with LLM-based review (Claude) to automatically review pull requests on GitHub.

## Prerequisites

- Docker and Docker Compose
- GitHub App credentials (for production)
- Anthropic API key (for LLM review)
- Redis (included in docker-compose)

## Environment Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Redis
REDIS_URL=redis://redis:6379/0

# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# GitHub App (for production webhook integration)
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=your_private_key_pem_content
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Or use personal token for development
GITHUB_TOKEN=your_personal_access_token

# Application Settings
LOG_LEVEL=INFO
ANALYSIS_MODE=hybrid  # static_only, llm_only, or hybrid
USE_REAL_APIS=false   # Set to true for production

# Experiments
EXPERIMENT_RESULTS_DIR=results/experiments
EXPERIMENT_RANDOM_SEED=42
```

## Local Development with Docker Compose

### 1. Build the containers

```bash
docker-compose build
```

### 2. Start the services

```bash
docker-compose up -d
```

This starts three services:
- **redis**: Message broker and job state storage
- **api**: FastAPI application (port 8000)
- **worker**: Celery worker for background jobs

### 3. Verify services are running

```bash
# Check service status
docker-compose ps

# Check API health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api
docker-compose logs -f worker
```

### 4. Test the API

```bash
# Manual review request
curl -X POST http://localhost:8000/review \\
  -H "Content-Type: application/json" \\
  -d '{
    "repo": "owner/repo-name",
    "base": "base_commit_sha",
    "head": "head_commit_sha",
    "pr": 42,
    "analysis_mode": "hybrid"
  }'

# Check job status
curl http://localhost:8000/jobs/{job_id}
```

## GitHub App Setup

### 1. Create a GitHub App

1. Go to GitHub Settings → Developer settings → GitHub Apps → New GitHub App
2. Configure:
   - **Name**: AI Code Reviewer (or your choice)
   - **Homepage URL**: Your deployment URL
   - **Webhook URL**: `https://your-domain.com/webhook`
   - **Webhook secret**: Generate a random secret
   - **Permissions**:
     - Repository permissions:
       - Contents: Read
       - Pull requests: Read & Write
       - Checks: Read & Write
   - **Subscribe to events**:
     - Pull request

3. Generate a private key and download it
4. Note your App ID

### 2. Install the App

1. Install the GitHub App on your target repositories
2. Note the installation ID (visible in the URL)

### 3. Configure Environment

Update `.env` with your GitHub App credentials:

```bash
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret
USE_REAL_APIS=true
```

## Production Deployment

### Using Docker Compose

1. Update `docker-compose.yml` for production:
   - Remove `--reload` from API command
   - Add resource limits
   - Configure proper logging
   - Use production-grade Redis

2. Deploy:

```bash
# Build production images
docker-compose -f docker-compose.yml build

# Start services
docker-compose up -d

# Monitor
docker-compose logs -f
```

### Healthcheck Endpoints

- **Basic health**: `GET /`
- **Detailed health**: `GET /health` (checks Redis connectivity)

Monitor these endpoints for service health.

## Analysis Modes

The system supports three analysis modes:

### 1. `static_only`
- Runs Semgrep and Bandit only
- Fast, deterministic results
- Good for catching common security issues and code smells

### 2. `llm_only`
- Runs Claude-based review only
- Slower, more nuanced analysis
- Good for logic errors and design issues

### 3. `hybrid` (default)
- Runs static analysis first
- Passes static findings to LLM as context
- LLM can verify/refine static findings
- Best overall coverage

Configure the default mode in `.env`:

```bash
ANALYSIS_MODE=hybrid
```

Or specify per-request via the API:

```json
{
  "repo": "owner/repo",
  "base": "abc123",
  "head": "def456",
  "analysis_mode": "static_only"
}
```

## Running Experiments

For research and evaluation, use the offline experiment framework:

### 1. Create experiment configuration

Edit `experiments/example_config.json`:

```json
{
  "name": "my_experiment",
  "repos": [
    {
      "url": "https://github.com/owner/repo.git",
      "base_sha": "base_commit",
      "head_sha": "head_commit",
      "pr_number": null
    }
  ],
  "modes": ["static_only", "llm_only", "hybrid"]
}
```

### 2. Run experiments

```bash
python scripts/run_experiments.py experiments/example_config.json
```

### 3. Evaluate results

```bash
python scripts/evaluate_results.py results/experiments/my_experiment_*.jsonl
```

## Monitoring

### Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f worker

# Redis logs
docker-compose logs -f redis
```

### Job State

Jobs are stored in Redis with 24-hour TTL:

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# List all jobs
KEYS job:*

# Get job details
GET job:{job_id}
```

## Troubleshooting

### API not responding

```bash
# Check if container is running
docker-compose ps api

# Check logs
docker-compose logs api

# Restart
docker-compose restart api
```

### Worker not processing jobs

```bash
# Check worker logs
docker-compose logs worker

# Verify Redis connection
docker-compose exec worker python -c "import redis; r=redis.from_url('redis://redis:6379/0'); print(r.ping())"

# Restart worker
docker-compose restart worker
```

### GitHub webhook not working

1. Check webhook secret is configured correctly
2. Verify webhook URL is accessible from GitHub
3. Check API logs for incoming webhook requests
4. Ensure GitHub App has correct permissions

### LLM review failing

1. Verify `ANTHROPIC_API_KEY` is set correctly
2. Check API quota/limits
3. Review worker logs for specific errors
4. Consider using `USE_REAL_APIS=false` for testing with mocks

## Scaling

### Horizontal Scaling

Scale workers for parallel processing:

```bash
docker-compose up -d --scale worker=4
```

### Resource Limits

Update `docker-compose.yml`:

```yaml
worker:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

## Security Considerations

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use webhook signature verification** - Currently marked as TODO in code
3. **Limit repository access** - Only install GitHub App on trusted repos
4. **Monitor API usage** - Track Anthropic API costs
5. **Use HTTPS** - Always use TLS in production
6. **Rotate secrets** - Regularly rotate GitHub App keys and webhook secrets

## Support

For issues or questions:
1. Check logs first
2. Review this documentation
3. Check GitHub Issues
4. Contact maintainers
