# AI-Assisted Code Review System

**Event-Driven Hybrid Analysis under Uncertainty**

A research prototype exploring how automated code review systems can behave predictably under latency, partial failure, and noisy probabilistic signals.

Rather than treating LLMs as authoritative reviewers, this system treats them as **uncertain components** embedded within a deterministic, event-driven pipeline that degrades safely when probabilistic analysis is slow or unavailable.

---

## The Problem

Automated code review tools face a fundamental tension:

| Approach | Strengths | Weaknesses |
|----------|-----------|------------|
| **Static analysis** | Fast, deterministic, reliable | Limited semantic understanding |
| **LLM-based review** | Expressive, catches design issues | Slow, costly, unreliable under failure |

Most existing systems either block developer workflows waiting for AI responses, or silently fail when probabilistic components are unavailable.

**This project asks:** How should review pipelines be architected so that uncertainty and latency do not compromise availability or trust?

---

## Key Insights

- Probabilistic review improves coverage but introduces latency risk
- Static analysis provides a reliable baseline under failure
- Hybrid designs work best when probabilistic reasoning is **constrained, not trusted blindly**
- In developer-facing systems, **availability and predictability matter more than completeness**

---

## Architecture

```
GitHub Pull Request
        │
        ▼
   ┌─────────┐
   │ Webhook │
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ FastAPI │
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │  Redis  │
   │  Queue  │
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ Celery  │
   │ Workers │
   └────┬────┘
        │
        ▼
┌───────────────────────────┐
│  Hybrid Analysis Engine   │
│                           │
│  ┌─────────┐ ┌─────────┐  │
│  │ Static  │ │   LLM   │  │
│  │Analysis │ │ Review  │  │
│  └─────────┘ └─────────┘  │
└───────────────────────────┘
        │
        ▼
   Inline PR Feedback
```

All components are decoupled—failures or delays in one stage don't propagate to others.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Non-blocking ingestion** | Webhook → queue separation |
| **Component isolation** | Deterministic and probabilistic paths are independent |
| **Explicit fallback** | Defined degradation when LLM fails or times out |
| **Predictable under load** | Static analysis always available as baseline |

---

## Analysis Modes

### Static Only
Runs deterministic analysis using Semgrep and Bandit. Fast, predictable, and serves as a safe baseline.

### LLM Only
Uses LLM-based semantic review. Captures higher-level logic and design issues, but subject to latency and availability constraints.

### Hybrid *(recommended)*
1. Runs static analysis first
2. Passes findings to LLM as structured context
3. LLM verifies, refines, or rejects static findings

The hybrid mode **constrains** probabilistic reasoning rather than relying on it blindly.

---

## Failure Handling

The system degrades gracefully:

```
Static analysis fails  →  Remaining analyzers continue
LLM inference times out  →  Fall back to static-only results
External APIs unavailable  →  Review availability preserved
```

Code review feedback remains available even when probabilistic components are unreliable.

---

## Getting Started

### Prerequisites

- Python 3.9+
- Redis server
- GitHub App or webhook access

### Installation

```bash
git clone https://github.com/yourusername/ai-code-review.git
cd ai-code-review
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your GitHub App credentials and Redis URL
```

### Running Locally

```bash
# Start Redis
redis-server

# Start Celery workers
celery -A app.worker worker --loglevel=info

# Start API server
uvicorn app.main:app --reload

# Expose webhook (for local development)
ngrok http 8000
```

### Running an Analysis

```bash
# Trigger analysis on a PR (manual testing)
python scripts/analyze_pr.py --repo owner/repo --pr 123 --mode hybrid

# Compare modes
python scripts/compare_modes.py --repo owner/repo --pr 123
```

---

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI application
│   ├── worker.py            # Celery task definitions
│   ├── webhook.py           # GitHub webhook handlers
│   └── analysis/
│       ├── static.py        # Semgrep/Bandit integration
│       ├── llm.py           # LLM review logic
│       └── hybrid.py        # Hybrid orchestration
├── scripts/
│   ├── analyze_pr.py        # Manual PR analysis
│   └── compare_modes.py     # Mode comparison experiments
├── tests/
└── experiments/             # Research experiment configs
```

---

## Research Applications

Beyond automation, the system supports controlled experimentation:

- **Coverage comparison:** Static vs LLM vs hybrid findings
- **Agreement analysis:** Overlap and disagreement between tools
- **Operational behavior:** Latency and availability under different modes

The goal is not to optimize accuracy, but to understand how different analysis strategies behave under realistic operational constraints.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| Queue | Redis |
| Workers | Celery |
| Static Analysis | Semgrep, Bandit |
| Integration | GitHub Webhooks |

---

## Limitations

- LLM inference introduces non-deterministic latency
- Research prototype, not a production CI service
- Evaluation focuses on behavior and failure modes, not ground-truth correctness

---

## Why This Matters

This project complements systems research on uncertainty-aware scheduling and tail behavior by examining how **probabilistic components interact with deterministic control logic**.

It demonstrates how system design choices can **surface uncertainty explicitly** rather than hiding it behind average-case behavior.

---

## Related Work

- [Semgrep](https://semgrep.dev/) - Static analysis engine
- [Bandit](https://bandit.readthedocs.io/) - Python security linter
- Dean & Barroso, "The Tail at Scale" (2013)

---

## Citation

```bibtex
@software{ai_code_review_system,
  author = {Shalini},
  title = {AI-Assisted Code Review: Event-Driven Hybrid Analysis under Uncertainty},
  year = {2025},
  url = {https://github.com/yourusername/ai-code-review}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Status

✅ Completed as an independent systems research prototype  
🔬 Designed for architectural exploration and controlled experimentation
