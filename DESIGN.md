# Design

## PCB JSON schema (`src/pcb_ai/schemas/pcb.py`, `schema_version: "1.0"`)

```json
{
  "schema_version": "1.0",
  "board": {"board_id": "...", "title": "...", "revision": "...", "layers": ["F.Cu", "..."], "thickness_mm": 1.6, "width_mm": 60.0, "height_mm": 40.0},
  "layers": [{"id": 0, "name": "F.Cu", "type": "signal"}],
  "components": [{"reference": "U3", "value": "...", "footprint": "...", "position": {"x":.., "y":..}, "rotation_deg": 0, "side": "top", "pads": ["U3:1", "..."], "uuid": "..."}],
  "footprints": [{"reference": "U3", "has_courtyard": true, "graphics_count": 6, "fab_layer_present": true}],
  "pads": [{"component_reference": "U3", "pad_number": "4", "position": {"x":.., "y":..} /* ABSOLUTE board coords */, "net_name": "SPI_CLK", "uuid": "u3-p4"}],
  "nets": [{"net_id": 3, "net_name": "SPI_CLK", "connected_pads": ["U3:4", "R8:1"], "connected_components": ["U3", "R8"]}],
  "tracks": [{"track_id": "...", "layer": "F.Cu", "start": {...}, "end": {...}, "width_mm": 0.12, "net_name": "SPI_CLK"}],
  "vias": [{"via_id": "...", "position": {...}, "diameter_mm": 0.6, "drill_mm": 0.3, "net_name": "VCC"}],
  "zones": [{"zone_id": "...", "layer": "B.Cu", "net_name": "GND", "polygon": [{"x":.., "y":..}]}],
  "rules": [{"rule_name": "pad_to_mask_clearance", "rule_type": "clearance", "value": 0.05, "unit": "mm"}]
}
```

Parsed by `pcb_ai.parser.kicad_pcb_parser.parse_kicad_pcb_file` from the
KiCad 6/7/8/9 S-expression format (via `sexpdata`). Design rule extraction
is best-effort (a handful of `setup` block values); KiCad's full design
rule engine is not reimplemented -- that responsibility stays with KiCad's
own DRC (see below).

## DRC schema (`src/pcb_ai/schemas/drc.py`, `schema_version: "1.0"`)

`kicad-cli pcb drc --format json` (KiCad 7+) emits:

```json
{
  "$schema": "https://schemas.kicad.org/drc.v1.json",
  "coordinate_units": "mm", "kicad_version": "...", "source": "board.kicad_pcb",
  "violations": [{"type": "clearance", "severity": "error|warning|ignore", "description": "...", "excluded": false,
                  "items": [{"description": "...", "pos": {"x":.., "y":..}, "uuid": "..."}]}],
  "unconnected_items": [...]
}
```

`pcb_ai.drc.normalizer.normalize_drc_report` converts this into
`DRCViolation` objects:
- `rule_type` is mapped from KiCad's internal rule id to a fixed
  `ViolationTaxonomy` enum (20+ categories from the spec's Phase 3 list;
  unmapped ids fall back to `OTHER`, never silently dropped).
- Each `items[].uuid` is resolved to a concrete `{type, reference, pad,
  net}` via `PCBGraph.resolve_uuid` -- **not** by asking the LLM.
- `required_value`/`actual_value` are extracted from the free-text
  description via a documented, best-effort regex (KiCad does not emit
  these as separate structured fields as of the schema versions checked).
- `raw_drc_message` and `raw` (the entire raw violation dict) are always
  preserved verbatim.
- `unconnected_items` (reported by KiCad separately from `violations`) are
  also normalized into `DRCViolation`s (taxonomy `UNCONNECTED`) so the rest
  of the pipeline treats them uniformly.

`kicad-cli` is invoked by `pcb_ai.drc.runner.run_kicad_drc`. If it is not
found on `PATH`/`KICAD_CLI_PATH`, the function returns
`DRCRunResult(executed=False, error=...)` -- it never fabricates
violations. `load_fixture_drc_report` loads a pre-recorded, real-schema
report for offline development/testing and marks the result
`fixture_used=True`.

## Diagnosis output schema (`src/pcb_ai/schemas/diagnosis.py`, `schema_version: "1.0"`)

Matches the spec's Phase 9 schema exactly (classification, summary,
affected_objects, driving_rule, root_cause, engineering_impact,
recommended_fix, evidence, uncertainty, requires_human_review), plus the
Phase 13 severity-preservation fields (`deterministic_severity`,
`llm_assessed_severity`, `severity_policy_version`) and the Phase 12
validation outcome (`validation_passed`, `validation_errors`).

`driving_rule.required_value`/`actual_value` accept either a string or a
number (`Union[str, float, int]`): live testing against the configured
LLM showed it reliably returns these as JSON numbers, not strings, and the
schema was fixed to match real model behavior rather than force a lossy
string coercion.

## Prompt design (`src/pcb_ai/prompts/violation_analysis.py`, Phase 24)

Prompts are versioned data (`PromptVersion` dataclass), not inline
f-strings buried in agent code, so `analysis_id`/`prompt_version` can be
recorded per run and prompts can be iterated (`violation_analysis_v2`,
...) without touching pipeline logic. The system prompt explicitly:
- states the DRC engine's finding is ground truth and must not be
  second-guessed,
- forbids inventing specs/dimensions/limits not present in supplied
  evidence,
- requires `insufficient_evidence: true` when evidence is inadequate,
- requires every evidence citation to reference a specific supplied
  source (DRC / PCB object / knowledge chunk id), and
- requires both `deterministic_severity` (echoed) and
  `llm_assessed_severity` to be distinguishable in the output.

## Agent / tool architecture (Phase 10)

`AgentToolbox` (`src/pcb_ai/agent/tools.py`) exposes eleven deterministic
tools (`list_violations`, `get_violation`, `get_component`, `get_pad`,
`get_net`, `get_connected_objects`, `get_nearby_objects`,
`get_applicable_rules`, `search_datasheet`, `search_engineering_knowledge`,
`get_drc_evidence`) as OpenAI function-tool schemas. `list_violations` was
added after live testing showed the agent had no way to discover which
`violation_id` a free-form question (e.g. "why is U3 pad 4 failing DRC?")
referred to, and would exhaust its tool-call budget guessing ids. Two
consumers:

1. `ViolationDiagnosisAgent` -- does **not** use tool-calling; it calls the
   same underlying deterministic functions directly (via `PCBGraph` /
   `PCBContextRetriever` / `KnowledgeRetriever`) to assemble evidence
   before a single LLM call. See ARCHITECTURE.md for why.
2. `InteractiveQueryAgent` (`src/pcb_ai/agent/query_agent.py`) -- a real
   tool-calling loop: the LLM receives `AgentToolbox.schemas`, decides
   which tools to call, receives tool results as `role="tool"` messages,
   and iterates (bounded by `max_iterations`) until it can answer without
   further tool calls, or the budget is exhausted (in which case it must
   say so rather than guess). Validated live: the configured model
   correctly calls `get_component` before answering a factual question
   about a component.

## RAG design (Phase 6/7)

`KnowledgeRetriever` (`src/pcb_ai/rag/retriever.py`):
- **Ingestion**: `.txt`/`.md`/`.pdf` files are chunked by
  `pcb_ai.rag.chunker.chunk_text`, which splits on explicit page markers
  (`--- page N ---`, inserted by the PDF extractor,
  `pcb_ai.rag.pdf_utils.extract_pdf_text`) and Markdown headers *before*
  applying a ~350-word sliding window with overlap -- so `page`/`section`
  provenance survives per chunk, rather than chunking blindly by character
  count.
- **Hybrid retrieval**: (1) deterministic component/net substring
  filtering, (2) violation-type keyword filtering, then (3) combined
  BM25 + TF-IDF-cosine scoring over the filtered candidates.
  - **Known limitation**: no real embedding endpoint was available in this
    environment (the configured LiteLLM/vLLM gateway's `/v1/embeddings`
    route returned 404 for the only model group visible to this API key).
    "Semantic" retrieval therefore uses TF-IDF (a sparse, lexical
    approximation), not a trained embedding model. `KnowledgeRetriever`'s
    public interface (`search`, `search_by_component`,
    `search_by_violation_type`, `index_document`, `get_source`) does not
    depend on this choice, so a real embedding backend (or
    FAISS/Chroma/Qdrant/pgvector) can be substituted later.
  - On the small bundled fixture corpus (10 chunks total), ranking quality
    is visibly imperfect (see `tests/test_rag.py` and the manual smoke
    test in session history) -- expected for lexical retrieval over a tiny
    corpus, and something a real embedding model + a larger corpus would
    substantially improve.

**Two separate `KnowledgeRetriever` instances exist in this project, by
design:**

1. `AnalysisService.knowledge_retriever` -- indexes `data/knowledge/` +
   `data/datasheets/` (small synthetic fixtures) and feeds the **live DRC
   diagnosis pipeline**'s evidence assembly (Phase 6/7 as used by
   `ViolationDiagnosisAgent`).
2. `KnowledgeBaseShowcase` (`src/pcb_ai/research/knowledge_showcase.py`) --
   indexes ~300 chunks from 12 **real** manufacturer datasheet PDFs curated
   from the reference `pcb_qa-4FEE` benchmark repository, exposed via
   `GET /knowledge/showcase/summary` / `POST /knowledge/showcase/search`
   and rendered in the frontend's "Knowledge Base" tab, purely to
   demonstrate the hybrid-retrieval RAG layer against rich, real-world
   content.

These are **intentionally not merged**: `pcb_qa-4FEE`'s real hardware
projects and the bundled synthetic demo board can both have a component
named e.g. "U3" that are completely different parts. If both corpora were
indexed into one retriever, a reference-based search during live diagnosis
could retrieve and cite the wrong real datasheet as evidence for the demo
board's violation -- silently defeating the evidence-grounding guarantee
the whole pipeline exists to provide. Keeping them separate avoids that
failure mode while still letting the RAG capability be demonstrated
against genuine content.

## Evidence validation (Phase 12, `src/pcb_ai/validation/evidence_validator.py`)

Runs after every LLM diagnosis (unless it's already an
`insufficient_evidence` fallback):
1. Every `affected_objects[].reference/pad/net` must exist on the real
   board (checked against `PCBGraph`, not just the retrieved context --
   catching hallucinated components/pads/nets anywhere on the board).
2. `driving_rule.required_value/actual_value` must match the deterministic
   DRC evidence within tolerance (0.01mm absolute or 5% relative).
3. Every `evidence[]` citation must resolve to a real source: DRC
   (`source_id == violation_id`), a real knowledge chunk id (exact match
   against the chunks actually supplied), or a real PCB object (component
   reference, net name, pad id, KiCad uuid, or one of a small set of
   generic category labels like `"nets"` that models sometimes use in
   place of a specific id).
4. Any failure: `validation_passed=False`, `requires_human_review=True`
   (forced), `classification.confidence`/`root_cause.confidence` halved,
   and the specific errors appended to `uncertainty`. The diagnosis
   content itself is preserved (not discarded), per Phase 12's
   "mark the response invalid... or retrieve additional evidence" guidance
   -- discarding a mostly-correct diagnosis over one loosely-labeled
   citation would be overly punitive; the confidence/human-review
   penalties make the uncertainty visible instead.

## Severity policy (Phase 13, `src/pcb_ai/severity/policy.py`)

A fixed `ViolationTaxonomy -> Severity` baseline table (critical:
short-circuit; high: clearance/zone-clearance/copper-to-edge/unconnected/
missing-connection/impedance/board-edge; medium: track-width/via/drill/
hole-to-hole/diff-pair/length-mismatch/annular-ring/other/unknown; low:
courtyard/silkscreen/footprint-library). `compute_deterministic_severity`
takes the more severe of this baseline and KiCad's own reported
error/warning severity -- it never downgrades. The LLM's own
`llm_assessed_severity` is preserved separately and never silently
replaces the deterministic value.
