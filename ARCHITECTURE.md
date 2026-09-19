# Architecture

## Design principle: evidence hierarchy

```
LEVEL 1  Deterministic truth        KiCad DRC (kicad-cli)
LEVEL 2  Structured design facts    PCB JSON / connectivity graph
LEVEL 3  External engineering data  Datasheets / design guidelines (RAG)
LEVEL 4  LLM reasoning              Interpretation / diagnosis / recommendation
LEVEL 5  Human approval             Final engineering decision
```

The LLM sits at Level 4: an **evidence-grounded reasoning layer**, never
the source of truth. It cannot detect violations, invent PCB facts, or
apply any change to the design (read-only in this version).

## Data flow

```
.kicad_pcb
   |
   v
KiCadPCBParser (src/pcb_ai/parser)
   |
   v
PCBDesign  (src/pcb_ai/schemas/pcb.py, schema_version "1.0")
   |                                   \
   v                                    v
kicad-cli pcb drc --format json     PCBGraph (src/pcb_ai/context/graph.py)
   |                                    (deterministic traversal +
   v                                     KiCad-uuid resolution)
raw DRC JSON report
   |
   v
normalize_drc_report()  (src/pcb_ai/drc/normalizer.py)
   -> DRCViolation[]  (schema_version "1.0", taxonomy-classified,
                       object references resolved via PCBGraph.resolve_uuid)
   |
   v
PCBContextRetriever.retrieve(violation)  (src/pcb_ai/context/retriever.py)
   -> ViolationContext: minimal, per-violation subset of the board
      (referenced components/pads/nets + their connected tracks/vias/zones
       + nearby geometry within a radius + applicable design rules)
   |
   v
KnowledgeRetriever.search_by_violation_type() / search_by_component()
   (src/pcb_ai/rag/retriever.py)
   -> KnowledgeChunk[] with document/page/section provenance
   |
   v
ViolationDiagnosisAgent.diagnose()  (src/pcb_ai/agent/pipeline.py)
   Stage 1  drc_interpretation             (deterministic)
   Stage 2  pcb_context_resolution         (deterministic, via PCBContextRetriever)
   Stage 3  engineering_knowledge_retrieval(deterministic, via KnowledgeRetriever)
   Stage 4-6 llm_reasoning                 (ONE constrained, json-mode LLM call)
   Stage 7  evidence_validation            (deterministic, src/pcb_ai/validation)
   Stage 8  structured_output              (ViolationDiagnosis, schema_version "1.0")
   |
   v
generate_report()  (src/pcb_ai/reporting/report_generator.py)
   -> human-readable Markdown engineering report
```

Every stage boundary is explicit in code (`AnalysisTrace.stages_completed`)
so the pipeline is auditable and reproducible (Phase 23 observability).

## Why deterministic evidence assembly, not LLM-driven retrieval, for the
## main diagnosis pipeline

The architecture spec is explicit: *"Do not ask the LLM to locate the
relevant PCB objects itself if the software can determine them
deterministically."* `ViolationDiagnosisAgent` therefore assembles all
evidence (PCB context, knowledge chunks) in plain Python **before** calling
the LLM once, in JSON mode, to synthesize the diagnosis. This keeps the
system auditable: every object/document that could have influenced the
answer is known in advance and validated afterward.

A second, complementary agent -- `InteractiveQueryAgent`
(`src/pcb_ai/agent/query_agent.py`) -- exists for free-form questions
("Why is U3 pad 4 failing DRC?") where the *scope* of relevant evidence
isn't known ahead of time. There, the LLM is given tool schemas
(`AgentToolbox`, `src/pcb_ai/agent/tools.py`) and decides which
deterministic lookups to call, matching the Phase 10 tool-calling example
in the spec. This agent is exposed via `pcb-ai query` and `POST /pcb/query`.

## Object identity: KiCad uuids as the ground truth link

Every pad, footprint, track, via, and zone parsed from the `.kicad_pcb`
file carries its native KiCad `uuid` (see `schemas/pcb.py`). `PCBGraph`
builds a `uuid -> object` index (`resolve_uuid`). The DRC normalizer uses
this index to convert KiCad's raw violation `items` (which only carry a
`uuid` and free-text `description`) into fully-resolved
`{type, reference, pad, net}` triples -- without any LLM guessing which
pad/component/net a violation refers to.

**Coordinate transform correctness:** KiCad pad `(at x y)` values are
*local* to their footprint. The parser rotates and translates them by the
footprint's own board position/rotation before storing `Pad.position`, so
spatial queries (`PCBGraph.get_nearby_objects`) operate in real board
coordinates. (This was caught and fixed via a unit test during
development -- see `tests/test_context.py::test_graph_nearby_objects_deterministic`.)

## Component inventory vs. existing repository

The workspace (`c:\Users\vishalkr\cept\pcb_ai_ml`) was **empty** at the
start of this work -- there was no pre-existing PCB-QA implementation,
parser, RAG stack, or API to extend. Everything under `src/pcb_ai/` was
built from scratch per the spec's Phase 0 instruction to reuse existing
abstractions "where appropriate"; since none existed, new abstractions
were created following the architecture's own naming (e.g. `PCBGraph`,
`KnowledgeRetriever`, `BaseLLMProvider`) so the code is directly
traceable to specific phases of the spec.

## Model/RAG abstraction (Phase 21/22)

- `BaseLLMProvider` (`src/pcb_ai/llm/base.py`) is the only interface the
  agent code depends on. `OpenAICompatibleProvider` implements it against
  any OpenAI-compatible chat-completions endpoint (validated live against
  a self-hosted vLLM/LiteLLM gateway serving `nemotron3-super-120b`).
  `MockLLMProvider` implements it for deterministic offline tests.
- `KnowledgeRetriever` (`src/pcb_ai/rag/retriever.py`) is not coupled to
  any particular vector database; see DESIGN.md for why TF-IDF + BM25 was
  used as the default in-process backend and how to swap in
  FAISS/Chroma/Qdrant/pgvector later without touching calling code.
