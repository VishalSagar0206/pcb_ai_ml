# Evaluation

## Scope and status: DEMONSTRATION RUN, not a validated research result

This document reports the output of one real, executed evaluation run
(`pcb-ai evaluate tests\fixtures\evaluation --out results`) against the
live configured LLM (`nemotron3-super-120b`, self-hosted vLLM/LiteLLM
gateway). It covers **one synthetic board, 4 labeled violations, 5
conditions = 20 LLM calls total.** It is a proof that the evaluation
*infrastructure* (Phase 17-20) works end-to-end, and an honest, real (not
fabricated) first data point -- **it is not a claim that this system
outperforms or underperforms PCB-QA or any other baseline** on any
research-representative dataset. See "What this does NOT show" below.

Raw artifacts (regenerated on every run, gitignored under `results/`):
`baseline_drc_only.json`, `baseline_raw_kicad.json`,
`baseline_pcb_json.json`, `baseline_rag.json`,
`ablation_full_pcb_json.json`, `ablation_results.json`, `results.csv`.

## Dataset

`tests/fixtures/evaluation/case_sample_board/`: the same synthetic board
used throughout this project (`board.kicad_pcb`, 4 components, 9 pads, 5
nets), the same recorded DRC report (`drc.json`, 4 violations: a clearance
violation, a track-width violation, a silkscreen/board-edge violation, and
an unconnected-net violation), and `labels.json` -- 4 expert-authored
ground-truth records (root cause, impact, recommendation, severity,
human-review expectation) written by the author of this implementation
acting as domain reviewer. **These labels are demonstration-quality, not
independently verified by a second engineer.**

## Results (actual, from the run described above)

| Condition | Classification acc. | Severity agree. | Human-review agree. | Evidence grounding | Hallucination rate | Mean tokens | Mean latency (ms) | Mean evidence words |
|---|---|---|---|---|---|---|---|---|
| `drc_only` | 0.75 | 0.50 | 0.00 | **1.00** | **0.00** | 2312 | 15574 | 70.75 |
| `raw_kicad` | 0.75 | 0.50 | 0.75 | 0.25 | 0.75 | 6164 | 29117 | 750.75 |
| `pcb_json` | 0.50 | 0.50 | 1.00 | **0.00** | **1.00** | 4069 | 23274 | 70.75 |
| `full_pcb_json` | 0.75 | 0.50 | 0.75 | 0.25 | 0.75 | 5699 | 23593 | 74.75 |
| `pcb_json_rag` | 0.75 | 0.50 | 0.50 | 0.50 | 0.50 | 3944 | 21766 | 70.75 |

(`classification_accuracy`/`severity_agreement`/`human_review_agreement`/
`evidence_grounding`/`hallucination_rate` are fractions over n=4 records;
see EXPERIMENTS.md for exact metric definitions and known simplifications.)

## Observations (from this run only -- n=4, not statistically meaningful)

- **`evidence_grounding_rate` dropped to 0 for `pcb_json` (no RAG) and
  only recovered to 0.50 once RAG evidence was added (`pcb_json_rag`).**
  Inspecting the raw per-record output
  (`results/baseline_pcb_json.json`) shows the model citing
  `source_type: "engineering_document"` or `"datasheet"` evidence items
  even when **no such documents were supplied** in that condition -- the
  evidence validator (Phase 12) correctly caught this as an unsupported
  citation in every one of the 4 records. This is exactly the failure
  mode the deterministic evidence-validation stage exists to catch, and
  it demonstrates the pipeline's grounding check is not a no-op: it
  meaningfully discriminates between conditions with and without real
  retrieved evidence.
- `drc_only` shows the *highest* grounding rate (1.00) simply because,
  with no PCB/knowledge context supplied, the model had fewer opportunities
  to cite a specific-but-unverifiable source -- it stuck to citing the DRC
  message itself. This is a useful reminder that "evidence grounding rate"
  must be read alongside how much evidence was actually offered, not in
  isolation.
- `mean_evidence_word_count` for `pcb_json` (70.75) and `full_pcb_json`
  (74.75) are nearly identical on this board -- expected, since the
  fixture board only has 4 components total, so "the entire board" and
  "the deterministically retrieved minimal context for one violation"
  are almost the same size. **This specific board cannot demonstrate the
  token-savings benefit of targeted retrieval that motivates the PCB-QA
  paradigm** -- a real board with dozens-to-hundreds of components would
  be needed to show that gap (see EXPERIMENTS.md, "What a real
  research-scale experiment would require").
- `raw_kicad` (raw file text instead of structured JSON) used roughly 2.7x
  the tokens of the structured conditions for comparable classification
  accuracy on this tiny board -- directionally consistent with the
  PCB-QA paper's core claim that structured representations are more
  token-efficient than raw file dumps, but again, n=4 on one tiny board is
  not sufficient to treat this as a validated finding.

## What this does NOT show

- It does **not** show that this system's diagnoses are correct in any
  general sense -- classification accuracy is measured against 4
  single-author labels on one synthetic board.
- It does **not** show retrieval precision/recall (no per-case relevant-
  document ground truth exists in this dataset -- reported as
  `NOT_COMPUTABLE`, not fabricated).
- It does **not** show cost (no pricing configured for the self-hosted
  model -- reported as `NOT_COMPUTABLE`).
- It does **not** compare against the original PCB-QA paper's dataset or
  results (no access to that dataset in this environment).

## Reproducing this run

```powershell
copy .env.example .env   # fill in your own CAF_MODEL_* credentials
.venv\Scripts\pcb-ai evaluate tests\fixtures\evaluation --out results
type results\ablation_results.json
```
