# AI Code Reviewer

A hybrid AI-powered code review system that combines static analysis tools (Semgrep, Bandit) with LLM-based review (Claude) to automatically analyze pull requests.

## Features

- **Three Analysis Modes**:
  - `static_only`: Fast static analysis with Semgrep and Bandit
  - `llm_only`: AI-powered review using Claude
  - `hybrid`: Combined approach for best coverage
  
- **GitHub Integration**: Automatic PR reviews via webhooks
- **Offline Experiments**: Research framework for comparing analysis modes
- **Evaluation Tools**: Metrics and overlap analysis between modes

## Quick Start

### 1. Setup Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker Compose

```bash
docker-compose up -d
```

### 3. Test the API

```bash
curl -X POST http://localhost:8000/review \\
  -H "Content-Type: application/json" \\
  -d '{
    "repo": "owner/repo",
    "base": "base_sha",
    "head": "head_sha",
    "analysis_mode": "hybrid"
  }'
```

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────┐
│   GitHub    │────▶│   API    │────▶│   Celery    │
│  Webhooks   │     │ (FastAPI)│     │   Worker    │
└─────────────┘     └──────────┘     └─────────────┘
                          │                  │
                          ▼                  ▼
                    ┌──────────┐     ┌─────────────┐
                    │  Redis   │     │  Analysis   │
                    │  (Jobs)  │     │   Engine    │
                    └──────────┘     └─────────────┘
                                            │
                         ┌──────────────────┼──────────────────┐
                         ▼                  ▼                  ▼
                    ┌─────────┐      ┌──────────┐      ┌──────────┐
                    │ Semgrep │      │  Bandit  │      │  Claude  │
                    └─────────┘      └──────────┘      └──────────┘
```

## Analysis Modes

### Static Only
- Runs Semgrep (security audit rules) and Bandit (Python security)
- Fast, deterministic results
- Good for CI/CD pipelines

### LLM Only
- Uses Claude for nuanced code review
- Catches logic errors and design issues
- Slower but more comprehensive

### Hybrid (Recommended)
- Runs static analysis first
- Passes findings to LLM as context
- LLM verifies and refines results
- Best overall coverage

## Running Experiments

For research and comparative analysis:

```bash
# Create experiment config
cat > experiments/my_experiment.json <<EOF
{
  "name": "mode_comparison",
  "repos": [
    {
      "url": "https://github.com/owner/repo.git",
      "base_sha": "abc123",
      "head_sha": "def456"
    }
  ],
  "modes": ["static_only", "llm_only", "hybrid"]
}
EOF

# Run experiments
python scripts/run_experiments.py experiments/my_experiment.json

# Evaluate results
python scripts/evaluate_results.py results/experiments/mode_comparison_*.jsonl
```

## Project Structure

```
├── src/
│   ├── api/              # FastAPI application
│   ├── analysis/         # Analysis engine and parsers
│   ├── experiments/      # Experiment framework
│   ├── integrations/     # GitHub, LLM, Git clients
│   ├── queue/            # Celery tasks
│   └── telemetry/        # Logging
├── config/               # Settings
├── experiments/          # Experiment configurations
├── scripts/              # CLI tools
├── tests/                # Test suite
├── docs/                 # Documentation
└── docker-compose.yml    # Docker setup
```

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Full deployment instructions
- [Execution Analysis](docs/EXECUTION_ANALYSIS.md) - System architecture deep-dive

## Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests

```bash
pytest
```

### Run Locally (without Docker)

```bash
# Start Redis
redis-server

# Start API
uvicorn src.api.main:app --reload

# Start Worker
celery -A src.queue.worker worker --loglevel=info
```

## Research Use Cases

This system is designed for MSCS-level research on code analysis:

1. **Mode Comparison**: Compare static vs LLM vs hybrid approaches
2. **Overlap Analysis**: Measure finding overlap between tools
3. **Performance Metrics**: Runtime, finding counts, severity distribution
4. **Reproducibility**: Deterministic experiments with mock clients

Example research questions:
- How much overlap exists between static and LLM findings?
- Which mode has better precision/recall? (with ground truth labels)
- What types of issues does each approach excel at?
- How does hybrid mode improve over individual approaches?

## Configuration

Key environment variables:

```bash
# Analysis
ANALYSIS_MODE=hybrid              # Default mode
USE_REAL_APIS=false              # Use mocks for testing

# APIs
ANTHROPIC_API_KEY=sk-...         # Claude API key
GITHUB_APP_ID=123456             # GitHub App ID
GITHUB_APP_PRIVATE_KEY=...       # GitHub App private key

# Experiments
EXPERIMENT_RESULTS_DIR=results/experiments
EXPERIMENT_RANDOM_SEED=42        # For reproducibility
```

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

- GitHub Issues: Report bugs or request features
- Documentation: See `docs/` directory
- Deployment Help: See `docs/DEPLOYMENT.md`
