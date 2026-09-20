# PCB DRC Intelligence

Evidence-grounded, LLM-assisted **interpretation and diagnosis** of
deterministic PCB design-rule-check (DRC) violations, extending the
paradigm introduced by *"PCB-QA: Evaluating LLMs over the First Printed
Circuit Board Design Question-Answer Dataset"* from passive PCB question
answering to active diagnosis of real DRC violations.

> **The deterministic KiCad DRC engine is the source of truth for what is
> wrong with a board. The LLM never detects violations -- it interprets,
> contextualizes, and explains violations that KiCad's DRC engine has
> already found, grounded in structured PCB data and retrieved engineering
> knowledge.**

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design,
[DESIGN.md](DESIGN.md) for schema/prompt/agent details,
[EVALUATION.md](EVALUATION.md) for the evaluation methodology and current
(demonstration-scale) results, [API.md](API.md) for the HTTP API,
[DEVELOPMENT.md](DEVELOPMENT.md) for setup/testing,
[TESTING_GUIDE.md](TESTING_GUIDE.md) for the full automated + manual/visual
QA checklist (including the frontend), and [EXPERIMENTS.md](EXPERIMENTS.md)
for the ablation/baseline experiment design.

## Pipeline

```
KiCad PCB (.kicad_pcb)
   -> PCB parser -> structured PCB JSON (schema v1.0)
   -> KiCad DRC (kicad-cli, or a recorded fixture for offline use)
   -> violation normalization (taxonomy + uuid-resolved object references)
   -> deterministic PCB context retrieval (minimal per-violation subset)
   -> engineering knowledge RAG (datasheets / guidelines, hybrid retrieval)
   -> LLM reasoning agent (structured JSON output only, json-mode enforced)
   -> evidence validation (rejects/downgrades ungrounded claims)
   -> engineering report + API/CLI
```

## Quick start

```powershell
# 1. Create a venv and install
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# 2. Configure credentials
copy .env.example .env
# edit .env: set CAF_MODEL_BASE_URL / CAF_MODEL_API_KEY / CAF_MODEL_ANALYSIS

# 3. Run the pipeline against the bundled synthetic fixture board
#    (no KiCad installation required -- uses a recorded DRC report)
.venv\Scripts\pcb-ai analyze tests\fixtures\sample_board.kicad_pcb `
    --fixture-drc tests\fixtures\sample_drc_report.json --out results

# 4. Read the generated report
type results\<analysis_id>_report.md
```

If `kicad-cli` (KiCad 7+) is installed and on PATH (or `KICAD_CLI_PATH` is
set), omit `--fixture-drc` to run live DRC.

## Docker (one-command full-stack starter)

```powershell
docker compose up --build
```

Then open http://localhost:8080. This builds and runs both containers:

- **`backend`** (`Dockerfile`) -- the FastAPI app on `:8000`, health-checked
  before the frontend starts.
- **`frontend`** (`frontend/Dockerfile`) -- the production Vite build served
  by nginx on `:8080`, which reverse-proxies `/api/*` to the backend
  container (same-origin from the browser's perspective, so no CORS setup
  is needed at runtime).

Works with **zero configuration** out of the box: if no `.env` exists at
the repo root, `CAF_MODEL_PROVIDER` defaults to `mock` (the offline
`MockLLMProvider`), so the demo/sample boards still fully diagnose without
any credentials. To get **real** LLM diagnosis, copy `.env.example` to
`.env` and either:

- fill in `CAF_MODEL_PROVIDER`/`CAF_MODEL_BASE_URL`/`CAF_MODEL_API_KEY` for
  this project's own gateway, **or**
- set `CAF_MODEL_PROVIDER=gemini` and `GEMINI_API_KEY=<your key>` to test
  with your own free Gemini API key instead (get one in ~30 seconds at
  https://aistudio.google.com/apikey, no credit card needed) -- see
  DEVELOPMENT.md's "Testing with a Gemini API key instead" for how this
  works with zero code changes and without disturbing the config above.

`docker compose` automatically reads that `.env` for variable substitution
into the containers.

KiCad itself is intentionally **not** installed in the backend image (see
DEVELOPMENT.md's "KiCad availability"); the bundled sample boards use
recorded DRC fixtures, so the full pipeline works end-to-end regardless.
`./results` and `./data/pcb_uploads` are mounted as volumes so evaluation
output and uploaded boards survive container restarts.

```powershell
docker compose down          # stop and remove the containers
docker compose logs -f       # follow both services' logs
```

## Windows startup without Docker

If Docker isn't available (or won't run) on a Windows machine, `start.bat`
is a one-command alternative that sets up and runs everything natively:

```powershell
start.bat
```

Double-click it in File Explorer, or run it from a terminal. It checks for
Python 3.10+ and Node.js, creates a virtual environment, installs backend
and frontend dependencies (only on first run), walks you through creating
`.env` with a Gemini API key if one doesn't exist yet, then starts the
backend and frontend each in their own console window and opens the app in
your browser. Safe to run again any time -- it skips work that's already
done and won't start a duplicate server if one's already running.

```powershell
stop.bat   # stops both servers
```

See TESTING_GUIDE.md's "Windows startup without Docker" section for full
details and troubleshooting.

## CLI commands

| Command | Purpose |
|---|---|
| `pcb-ai analyze <board.kicad_pcb>` | Full pipeline: parse -> DRC -> diagnose -> report |
| `pcb-ai drc <board.kicad_pcb>` | Run/normalize DRC only |
| `pcb-ai explain <board.kicad_pcb> --violation <id>` | Diagnose a single violation |
| `pcb-ai report <board.kicad_pcb>` | Print/save the human-readable report |
| `pcb-ai query <board.kicad_pcb> --question "..."` | Free-form Q&A via tool-calling agent |
| `pcb-ai index-knowledge <dir>` | Ingest datasheets/guidelines into a persisted chunk index |
| `pcb-ai evaluate <evaluation_dir>` | Run baseline/ablation experiments (Phase 17-20) |
| `pcb-ai doctor` | Report kicad-cli/LLM/knowledge-dir environment status |

All commands accept `--fixture-drc <path>` to use a recorded DRC JSON
report instead of invoking `kicad-cli` (useful when KiCad isn't installed).

## Running the API

```powershell
.venv\Scripts\uvicorn pcb_ai.api.app:app --host 0.0.0.0 --port 8000
```

See [API.md](API.md) for endpoints.

## Frontend (visual showcase)

A React + TypeScript + Tailwind + Framer Motion + Recharts dashboard lives in
[frontend/](frontend). It provides a dashboard-style Board Explorer (live
stat cards + an interactive PCB canvas with real component/pad/track/via/
zone coordinates and DRC violations highlighted in place, paired with an
evidence-grounded diagnosis panel), an animated pipeline architecture
explainer, a Knowledge Base tab demonstrating the hybrid-retrieval RAG
layer against real component datasheets (curated from
[pcb_qa-4FEE](pcb_qa-4FEE), ~300 chunks / 12 real manufacturer PDFs, with
live search), an evaluation dashboard driven by real ablation results, and
a research-lineage section referencing the same reference benchmark.

```powershell
# Terminal 1: backend
.venv\Scripts\uvicorn pcb_ai.api.app:app --host 127.0.0.1 --port 8931

# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/. See [frontend/README.md](frontend/README.md)
for details.

## Repository layout

```
src/pcb_ai/
  schemas/        Versioned pydantic schemas (PCB, DRC, diagnosis, knowledge, context)
  parser/         .kicad_pcb -> structured PCB JSON
  drc/            kicad-cli invocation + DRC JSON normalization
  context/        PCB relationship graph + per-violation context retriever
  rag/            Document chunking + hybrid (BM25 + TF-IDF) knowledge retriever
  llm/            Provider-agnostic LLM interface + OpenAI-compatible adapter + mock
  prompts/        Versioned prompts
  agent/          Multi-stage diagnosis pipeline + tool registry + interactive query agent
  severity/       Deterministic severity policy
  validation/     Evidence validator (Phase 12)
  reporting/      Human-readable engineering report generator
  eval/           Baseline/ablation experiments + metrics + runner
  api/            FastAPI app
  cli/            Typer CLI
  observability/  Logging + trace recording
  service.py      End-to-end orchestration used by both API and CLI
tests/            Unit/integration/e2e tests + fixtures (sample board, DRC report,
                  knowledge/datasheet documents, a demo evaluation dataset)
```

## Known limitations (see docs for detail)

- No KiCad installation is available in the development environment used to
  build this; DRC integration was validated against recorded fixtures and
  the real `kicad-cli pcb drc --format json` schema (documented from
  authoritative sources), not a live KiCad process. See
  [DEVELOPMENT.md](DEVELOPMENT.md).
- The "semantic" vector retrieval backend is TF-IDF, not a trained
  embedding model (no embedding endpoint was available); see
  [DESIGN.md](DESIGN.md).
- The evaluation results in [EVALUATION.md](EVALUATION.md) are from one
  small synthetic demonstration board, not a validated research-scale
  dataset. No accuracy claims beyond this demo run are made.
