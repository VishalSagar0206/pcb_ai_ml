# Experiments (Phase 18/20)

## Implemented ablation conditions (`src/pcb_ai/eval/experiments.py`)

| Condition | Evidence given to the LLM | Corresponds to |
|---|---|---|
| `drc_only` | DRC message/evidence only | Baseline A / Experiment 1 |
| `raw_kicad` | DRC evidence + a raw `.kicad_pcb` text excerpt (up to 6000 chars) | Baseline B |
| `pcb_json` | DRC evidence + deterministically retrieved, minimal PCB context | Baseline C / Experiments 2 & 7 |
| `full_pcb_json` | DRC evidence + the entire parsed PCB JSON (no filtering) | Experiment 6 |
| `pcb_json_rag` | DRC evidence + retrieved PCB context + engineering-knowledge RAG | Baseline D / Experiment 4 |

All five conditions reuse the exact same prompt template and structured
output schema (`synthesize_diagnosis`, `src/pcb_ai/agent/pipeline.py`) --
only the evidence-assembly step differs -- so any measured difference is
attributable to the evidence, not prompt wording.

**Not implemented as a single-shot ablation condition:** Baseline E (DRC +
PCB JSON + RAG + tool-based agent). The tool-calling agent infrastructure
itself exists and is validated (`InteractiveQueryAgent`,
`src/pcb_ai/agent/query_agent.py`, exposed via `pcb-ai query` /
`POST /pcb/query`), but reconciling free multi-turn tool use with the
strict single-call JSON-schema output used for structured diagnosis
required a more involved multi-turn-then-finalize design than the current
scope covers. This is explicitly flagged rather than faked, per the
architecture spec's research-integrity instructions.

## Running the experiments

```powershell
.venv\Scripts\pcb-ai evaluate tests\fixtures\evaluation --out results
```

This discovers every `<case>/board.kicad_pcb` + `<case>/labels.json`
subdirectory under the given path, runs all five conditions above against
every labeled violation, and writes:

```
results/baseline_drc_only.json      -- per-record raw diagnosis + metadata, condition drc_only
results/baseline_raw_kicad.json     -- ... condition raw_kicad
results/baseline_pcb_json.json      -- ... condition pcb_json
results/baseline_rag.json           -- ... condition pcb_json_rag
results/ablation_full_pcb_json.json -- ... condition full_pcb_json
results/ablation_results.json       -- aggregate metrics per condition
results/results.csv                 -- one row per (condition, violation) with the
                                        model/method/board/violation_type/accuracy/
                                        precision/recall/f1/grounding_score/
                                        hallucination_rate/latency/tokens/cost columns
```

## Metrics (Phase 19, `src/pcb_ai/eval/metrics.py`)

Computed per record and aggregated per condition:
`classification_accuracy`, `severity_agreement_rate`,
`human_review_agreement_rate`, `mean_root_cause_overlap` /
`mean_recommendation_overlap` (heuristic Jaccard word-overlap against the
expert free-text label -- **not** a substitute for a real NLG metric like
ROUGE/BERTScore, used only because no such dependency exists in this
project), `evidence_grounding_rate` (fraction with
`validation_passed=True`), `hallucination_rate` (fraction with
`validation_passed=False` or `insufficient_evidence=True`),
`mean_unsupported_claims`, `mean_evidence_word_count` (the
context-size comparison the spec specifically asks for --
retrieved (`pcb_json`) vs. full (`full_pcb_json`) context size),
`mean_total_tokens`, `mean_latency_ms`.

**Explicitly `NOT_COMPUTABLE`, not fabricated:** `retrieval_precision` /
`retrieval_recall` (would require per-case, human-labeled "relevant
document" ground truth, which the demo dataset does not have) and `cost`
(no pricing is configured for the evaluated self-hosted model). Both are
reported as literal `NOT_COMPUTABLE: ...` strings in every result file
rather than a fabricated number, per the spec's research-integrity
requirement.

`precision`/`recall`/`f1` in `results.csv` are, for this demo dataset,
identical to the binary classification-match indicator per record (not a
true multi-class confusion-matrix computation) -- the 4-violation, 1-case
demo dataset is too small for a meaningful per-class precision/recall
breakdown. This simplification is documented, not hidden.

## A demonstration run was executed (see EVALUATION.md for results)

`tests/fixtures/evaluation/case_sample_board/` (the same synthetic board
and DRC fixture used throughout this project, with 4 hand-authored expert
labels) was evaluated end-to-end against the live configured LLM
(`nemotron3-super-120b`) across all five conditions -- 20 real API calls,
no simulated/fabricated results. See EVALUATION.md for the numbers and
their (narrow, single-board) scope.

## What a real research-scale experiment would require

1. A dataset of real KiCad boards with genuine DRC violations across many
   violation types and board sizes (the current demo board is
   intentionally tiny -- 4 components -- so `full_pcb_json` and
   `pcb_json` context sizes are nearly identical; a real board with
   hundreds of components would show the token-savings benefit of
   targeted retrieval the PCB-QA paradigm specifically motivates).
2. Multiple independent expert annotators per violation (for inter-rater
   agreement) rather than one author's hand-written labels.
3. A real embedding model for the RAG backend (see DESIGN.md) instead of
   TF-IDF, to properly evaluate retrieval precision/recall.
4. Pricing information for the evaluated model, to compute `cost`.
