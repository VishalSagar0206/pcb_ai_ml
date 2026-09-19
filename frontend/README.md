# PCB DRC Intelligence — Frontend

A React (Vite + TypeScript + Tailwind v4 + Framer Motion + Recharts) visual
showcase for the PCB DRC Intelligence backend: an interactive, real-coordinate
PCB board canvas with DRC violations highlighted in place, an evidence-grounded
diagnosis panel, an animated pipeline-architecture explainer, an evaluation
dashboard driven by real (non-fabricated) ablation results, and a research
lineage section referencing the original PCB-QA benchmark.

## Prerequisites

- The backend API running (see the main [README](../README.md)):
  ```powershell
  cd ..
  .venv\Scripts\uvicorn pcb_ai.api.app:app --host 127.0.0.1 --port 8931
  ```
  (Any port works — just keep it in sync with `vite.config.ts`'s proxy target.)

## Setup & run

```powershell
npm install
npm run dev
```

Open http://localhost:5173/. The Vite dev server proxies `/api/*` to the
backend (see `vite.config.ts`), so no CORS configuration is needed in dev.

## Testing

```powershell
npm run test         # Vitest: hooks + pure helpers, jsdom, no network (see ../TESTING_GUIDE.md #2)
npm run test:watch   # same, in watch mode
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

See [../TESTING_GUIDE.md](../TESTING_GUIDE.md) for the full automated +
manual/visual QA checklist covering this app.

## Structure

```
src/
  api/client.ts            Typed fetch wrapper for every backend endpoint
  types/                   TypeScript types mirroring the backend's pydantic schemas
  hooks/useAnalysis.ts      React hooks for analysis state + violation detail fetching
  test/                     Vitest unit tests for hooks + lib/format.ts (jsdom, mocked API client)
  components/
    board/                 PCBCanvas (SVG board renderer) + LayerToggle
    violations/             ViolationList + DiagnosisPanel (evidence-grounded diagnosis UI)
    pipeline/               PipelineDiagram (animated 7-stage architecture explainer)
    knowledge/              KnowledgeBasePage (real-datasheet RAG showcase: document grid + live hybrid search)
    evaluation/             EvaluationDashboard (Recharts bar/radar/table from real eval data)
    research/               ResearchLineage (PCB-QA reference project stats)
    layout/                 AppHeader (tab nav), BoardExplorer, PipelinePage (page compositions),
                            StatCard + Skeleton (shared dashboard-chrome components)
```

## Key implementation notes

- **Real board coordinates**: `PCBCanvas` renders components/pads/tracks/vias/
  zones/violation-markers directly from the backend's absolute-mm-coordinate
  PCB JSON (`GET /pcb/board/{analysis_id}`) — no synthetic/mock layout.
- **Wheel-zoom**: uses a native (non-passive) `wheel` event listener attached
  via `useEffect`, not React's synthetic `onWheel`, because browsers may
  register competing passive listeners for touchpad pinch/scroll gestures
  that silently defeat `event.preventDefault()` in the synthetic handler.
- **Demo caching**: `POST /pcb/demo` runs the bundled small sample board once
  (cached server-side under `analysis_id="demo"`) so the app loads instantly
  on repeat visits instead of re-running live LLM diagnosis every time.
- **Sample-board switcher**: `BoardExplorer`'s toolbar includes a
  Small/Medium/Large segmented control (`components/layout/SampleSwitcher.tsx`)
  backed by `GET /pcb/samples` (list + cached status) and
  `POST /pcb/samples/{id}/analyze` (run-once-then-cache, mirroring the demo
  endpoint's per-sample lock). Medium (13 components, 8 violations including
  a CRITICAL short circuit) and Large (26 components, 4 violations) were
  purpose-built via `scripts/generate_sample_boards.py` to stress-test canvas
  zoom/pan, violation-list scrolling, and taxonomy/severity badge coverage
  beyond the original 4-violation demo board.
- **Layer toggle**: a compact 4-mode segmented control (All / Top / Bottom /
  Outline) in `components/board/LayerToggle.tsx` -- replaced an earlier design
  that listed every raw KiCad layer name (a dozen buttons, most with no
  distinct rendering) in a cluttered wrapping row. "Outline" mode hides all
  copper/pads/vias/components and shows only the board edge + violation
  markers, useful for seeing violation spatial distribution at a glance on
  larger boards.
- **Concurrency**: the backend offloads blocking LLM/pipeline calls to a
  thread pool (`run_in_threadpool`) so the event loop stays responsive while
  a multi-violation diagnosis run is in progress — verified by confirming
  `/health` responds instantly during a live `/pcb/demo` run.
- **Fixed-viewport shell layout**: the app root uses `h-screen` + `flex-col`
  with `<main>` as the single `overflow-y-auto` scroll region (not
  `min-h-screen` on the root), so `h-full` reliably propagates down to the
  Board Explorer's 3-column grid instead of silently collapsing to
  content-height. This was a real bug found during review ("board explorer
  looks small") -- `min-h-screen` on the root only guarantees a *minimum*
  height, it doesn't give flex children a definite height to fill.
- **Knowledge Base showcase RAG demo**: real component datasheets (curated
  from `pcb_qa-4FEE`, ~300 chunks across 12 PDFs) indexed into a
  **separate** retriever from the live diagnosis pipeline's own knowledge
  base -- see `pcb_ai.research.knowledge_showcase` for why mixing them
  would risk cross-contaminating evidence citations (the real
  AcornRobotElectronics board also happens to have a "U3", a different
  part than the synthetic demo board's "U3").

## Build

```powershell
npm run build
```

Outputs to `dist/`. Serve behind any static file server, pointed at a
deployed backend (update the proxy/base URL in `vite.config.ts` or serve
via a reverse proxy that maps `/api` to the backend).
