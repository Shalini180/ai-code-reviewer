# Goal
Add an evaluation mode that can replay PRs in three configurations (static-only, llm-only, hybrid) and log structured findings for precision/recall and latency analysis.

## Proposed Changes
---
### src/api/models.py
- The `AnalysisMode` enum already exists. Ensure it is used throughout the codebase instead of raw strings.
- Add docstrings/comments if needed.

---
### config/settings.py
- Add a new boolean flag `evaluation_mode: bool = False` to enable offline evaluation paths.
- Update comments to clarify its purpose.

---
### src/analysis/engine.py
- Update the `analyze` method signature to accept `mode: AnalysisMode | str = None`.
- Normalize the incoming mode to `AnalysisMode` (support both enum and string).
- Adjust logic to use the enum values (`STATIC_ONLY`, `LLM_ONLY`, `HYBRID`).
- Ensure that when `mode` is `STATIC_ONLY` only static analysis runs, when `LLM_ONLY` only LLM runs, and `HYBRID` runs both as before.

---
### src/analysis/static.py & src/integrations/llm.py
- No functional changes needed; they already return `Finding` objects.
- Ensure that findings from static tools are mapped to the new normalized schema (see below).

---
### src/analysis/finding_schema.py (new file)
- Define a unified `NormalizedFinding` dataclass / Pydantic model matching the required schema:
```python
class NormalizedFinding(BaseModel):
    id: str
    source: Literal["static", "llm", "hybrid"]
    file: str
    line: int
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    category: Literal["security", "bug", "style", "performance", "other"]
    message: str
    suggested_fix: Optional[str] = None
```
- Provide helper functions to convert existing `Finding` objects to this schema.

---
### evaluation/run_evaluation.py (new module)
- CLI‑style script (callable via `python -m evaluation.run_evaluation`).
- Accept arguments: `--pr-list <json_file>` or a directory of diff files.
- For each PR:
  1. Load diffs (use existing `DiffParser`).
  2. Call `AnalysisEngine.analyze` three times with each `AnalysisMode`.
  3. Measure execution time with `time.perf_counter()`.
  4. Convert findings to `NormalizedFinding` and store in a JSONL line per run:
     ```json
     {"pr_id": "<id>", "analysis_mode": "static_only", "latency_ms": 123, "findings": [...], "timestamp": "ISO8601"}
     ```
- Write all rows to `results/evaluation/<timestamp>.jsonl`.

---
### evaluation/compute_metrics.py (new module)
- Load the JSONL file produced by the runner and a ground‑truth JSON file mapping `pr_id` → list of true issue identifiers.
- For each mode compute:
  * True Positives = findings that match a ground‑truth issue (match on `file`, `line`, and `category`).
  * False Positives, False Negatives.
  * Precision, Recall, F1, False‑positive rate.
  * Average latency per PR.
- Print a concise table to console and write a JSON report to `results/evaluation/metrics_<timestamp>.json`.

---
### tests
- Add unit tests for the conversion helper (`Finding` → `NormalizedFinding`).
- Add integration test that runs `run_evaluation` on a tiny synthetic PR fixture (two‑line diff) and checks that the JSONL file is created with three entries.

## Verification Plan
- **Automated**: Run the new unit tests with `pytest`. Ensure coverage > 80% for the new modules.
- **Manual**: Execute `python -m evaluation.run_evaluation --pr-list tests/fixtures/prs.json` and verify the JSONL output.
- Run `python -m evaluation.compute_metrics --results <jsonl> --ground_truth tests/fixtures/ground_truth.json` and inspect the printed metrics.
- Ensure that the existing pipeline (when `settings.evaluation_mode` is False) behaves exactly as before.

## Non‑Prod Safety
- The new `evaluation_mode` flag defaults to `False` so production runs never trigger the offline harness.
- The runner does **not** call any external APIs; it only uses local static tools and the LLM reviewer (which can be mocked or run with a stub model).
- No GitHub or Anthropic credentials are accessed when `evaluation_mode` is True.

## User Review Required
- Confirm the overall approach and the naming of the new flag (`evaluation_mode`).
- Approve the addition of the `NormalizedFinding` schema and its placement.
- Approve the CLI interface design for the evaluation scripts.
