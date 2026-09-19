# Testing Guide

This is the single reference for testing PCB DRC Intelligence end-to-end:
automated backend tests, automated frontend checks, and a manual/visual QA
checklist for the React frontend. It complements (does not replace)
[DEVELOPMENT.md](DEVELOPMENT.md) (setup, environment variables, KiCad/LLM
provider details) and [API.md](API.md) (endpoint reference).

## 1. Automated backend tests

```powershell
.venv\Scripts\python -m pytest tests\ -v
```

48 tests, no network access required (all LLM calls go through a
deterministic `MockLLMProvider` unless you explicitly point `.env` at a
live provider). Covers: KiCad parser (incl. footprint-local pad coordinate
transform regression), DRC normalization/taxonomy mapping, PCB context
graph + retriever, RAG chunker/retriever, severity policy, evidence
validator (incl. fabricated-reference/citation rejection and the accepted
generic-label set), diagnosis pipeline failure handling (invalid JSON,
schema violation, provider error), report generator, agent tool registry,
and one full end-to-end pipeline test.

Run a single test file or a keyword-filtered subset while iterating:

```powershell
.venv\Scripts\python -m pytest tests\test_evidence_validator.py -v
.venv\Scripts\python -m pytest tests\ -k "drc or parser" -v
```

## 2. Automated frontend checks

From `frontend/`:

```powershell
npm run test                            # Vitest unit/hook tests (jsdom, no network)
npx tsc --noEmit -p tsconfig.app.json   # typecheck
npm run build                           # production build; also re-runs tsc via `tsc -b`
```

`npm run test` runs 28 tests across 3 files with no network access
(`vitest.config` lives in `vite.config.ts`'s `test` key; jsdom environment;
`@testing-library/react` for hook rendering):

- `src/test/format.test.ts` -- pure formatting/color helpers
  (`severityColor`, `ruleTypeLabel`, `formatMs`, `formatPercent`, `clamp`).
- `src/test/validateBoardFile.test.ts` -- client-side upload validation
  (extension, empty file, 20MB size cap, case-insensitivity, boundary
  value).
- `src/test/useAnalysis.test.tsx` -- the `useAnalysis` and
  `useViolationDetail` hooks, with the API client module mocked via
  `vi.mock('../api/client')`: demo auto-load on mount, error handling
  without a stuck loading state, sample switching, upload validation
  short-circuiting the network call, successful upload, and violation-detail
  fetch/error/missing-id paths.

Use `npm run test:watch` for a watch-mode loop while iterating on a hook or
helper. Run a single file with `npx vitest run src/test/format.test.ts`.

A clean build currently produces roughly:

| Chunk | Size (gzip) | Loaded when |
|---|---|---|
| `index-*.js` (app shell + Board Explorer) | ~390KB (~123KB) | always |
| `EvaluationDashboard-*.js` (Recharts) | ~412KB (~116KB) | Evaluation tab visited |
| `KnowledgeBasePage-*.js` | ~8KB (~3KB) | Knowledge Base tab visited |
| `PipelinePage-*.js` | ~8KB (~3KB) | Pipeline Architecture tab visited |
| `ResearchLineage-*.js` | ~6KB (~2KB) | Research Lineage tab visited |

The four secondary tabs are lazy-loaded (`React.lazy` + `Suspense` in
`src/App.tsx`) specifically so the ~600KB-uncompressed Recharts dependency
never loads unless the user actually opens the Evaluation tab. If a future
change makes the main chunk balloon again, check `App.tsx` still lazy-loads
everything except `BoardExplorer`. Test files are excluded from this build
output automatically (Vite only bundles what's imported from `main.tsx`).

## 3. Running both servers for manual/visual testing

```powershell
# Terminal 1 -- backend (pick a free port; 8931 avoids common local collisions)
.venv\Scripts\uvicorn pcb_ai.api.app:app --host 127.0.0.1 --port 8931

# Terminal 2 -- frontend
cd frontend
npm run dev   # http://localhost:5173, proxies /api to the backend (vite.config.ts)
```

Confirm both are up before testing:

```powershell
Invoke-RestMethod http://127.0.0.1:8931/health   # {"status":"ok","kicad_available":false}
Invoke-WebRequest http://localhost:5173 -UseBasicParsing | select StatusCode
```

**No KiCad installation is assumed.** `kicad_available` will correctly read
`false` in most dev environments -- this is expected, not a bug. All three
bundled sample boards use recorded DRC fixtures (`fixture_used: true`)
instead of a live `kicad-cli` run, so the full diagnosis pipeline still
works end-to-end without KiCad installed. See DEVELOPMENT.md's "KiCad
availability" section to test against a real install.

### 3.1 Or: the one-command Docker stack

```powershell
docker compose up --build   # http://localhost:8080
```

Builds and runs both containers (`Dockerfile` for the backend on `:8000`,
`frontend/Dockerfile` for an nginx-served production build on `:8080` that
proxies `/api/*` to the backend). Works with zero configuration (defaults
to the offline `MockLLMProvider` if no root `.env` is present) -- see the
README's "Docker" section for details. Useful for a from-clean-checkout
smoke test that doesn't depend on your local Python/Node toolchain at all:

```powershell
Invoke-RestMethod http://localhost:8000/health        # backend, direct
Invoke-RestMethod http://localhost:8080/api/health     # backend, via nginx proxy -- must match the direct call
docker compose logs -f backend                         # watch live diagnosis progress
docker compose down                                    # tear down when finished
```

### 3.2 This is the exact hand-off flow for someone testing with their own Gemini API key

The whole point of `CAF_MODEL_PROVIDER=gemini` (see DEVELOPMENT.md) is that
a teammate/friend can test the **entire** project end-to-end with nothing
but Docker and a free Gemini key -- no Python/Node install, no access to
this project's own Nemotron credentials. The message to send them is
literally:

> 1. Install Docker Desktop.
> 2. Clone/copy this repo.
> 3. Get a free Gemini API key at https://aistudio.google.com/apikey
>    (no credit card needed).
> 4. `copy .env.example .env`, then edit two lines in `.env`:
>    `CAF_MODEL_PROVIDER=gemini` and `GEMINI_API_KEY=<their key>`.
> 5. `docker compose up --build`
> 6. Open http://localhost:8080 and click around -- Board Explorer's
>    Small/Medium/Large sample switcher is the best starting point. The
>    first analysis of each sample board makes real Gemini calls and takes
>    roughly 1-4 minutes; everything after that is instant (server-side
>    cached per board).
> 7. If your friend is on a **free-tier** key: quota resets daily and is
>    fairly limited. If violations come back saying "Diagnosis unavailable"
>    after a bunch of testing, that's Gemini's free-tier daily request cap
>    for that model, not a bug -- check
>    https://ai.google.dev/gemini-api/docs/rate-limits. On a **paid/billed**
>    key this isn't a concern (much higher limits) -- no special pacing
>    needed.

To verify this flow yourself before sending it to anyone, in a **separate**
`.env` (or by temporarily setting these two lines in the real one) run:

```powershell
docker compose up --build
docker compose logs -f backend   # confirm calls go to generativelanguage.googleapis.com, not the Nemotron gateway
```

Then click through a sample board in the browser and confirm a diagnosis
renders with a populated Evidence section and a "validation passed"
banner, exactly as with the default Nemotron provider -- the whole point
of the shared `OpenAICompatibleProvider` is that the rest of the pipeline
(context retrieval, evidence validation, severity policy, reporting) is
completely provider-agnostic and shouldn't behave any differently.

**What live testing during development of this feature actually found**
(so you know what's expected vs. a real bug): a real Gemini API key
correctly produced valid, evidence-grounded diagnoses through this exact
pipeline (confirmed via `tests/test_llm_factory.py`'s design + a live
run). Two real, non-bug failure modes were also observed and are both
already handled gracefully by the existing pipeline (falls back to
`insufficient_evidence` + `requires_human_review`, never crashes, never
fabricates):
- **`503 UNAVAILABLE` ("model currently experiencing high demand")** --
  transient; `OpenAICompatibleProvider` now retries up to 5 times with
  backoff (bumped from the SDK's default of 2) specifically because of
  this.
- **`429 RESOURCE_EXHAUSTED` ("quota exceeded")** -- Gemini's newest
  "flash" model tier (e.g. `gemini-3.6-flash`) had a **20-requests/day**
  free-tier cap on the test key used, nowhere near enough for real usage.
  `GEMINI_DEFAULT_MODEL` (`src/pcb_ai/llm/factory.py`) was deliberately
  set to `gemini-2.5-flash-lite` instead, which has a substantially more
  generous free-tier daily quota and produced equally valid diagnoses in
  testing. If your friend's key still hits quota limits on flash-lite,
  that's a Gemini account/region-specific free-tier limit, not something
  this project controls -- see the links above.

## 4. Manual / visual QA checklist

Test at a **laptop viewport** (1280-1440px wide, not mobile) unless a step
says otherwise. If your OS uses display scaling (e.g. Windows at 125-150%),
remember your *effective* CSS viewport is smaller than the physical
resolution -- a 1920x1200 panel at 150% scaling is only ~1280x800 CSS px.

### 4.1 Board Explorer (default tab)

1. **Sample switcher** (Small / Medium / Large, top-right toolbar):
   - `Small` should be selected and loaded instantly on first page load
     (cached demo board, 4 violations).
   - Click `Medium` (13 components, 9 violations incl. one `CRITICAL`
     short-circuit) and `Large` (26 components, 5 violations). First
     analysis of each is a **live LLM run** and takes roughly 1-4 minutes
     (visible via the lightning-bolt icon on not-yet-cached samples and a
     spinner while active); subsequent switches are instant (cached
     server-side per `analysis_id`).
   - Stat cards (Total Violations, Critical/High, Human Review, Avg.
     Confidence, Board Size) should update to match the selected board.
2. **Layer toggle** (All Layers / Top / Bottom / Outline):
   - `Outline` should hide all copper/pads/vias/components and show only
     the board edge + violation markers -- useful for seeing violation
     spatial distribution at a glance on the Large board.
   - `Top` / `Bottom` filter copper/components by side (current sample
     boards place everything on the top side, so these will look identical
     to `All Layers` until a sample with bottom-side components exists).
3. **Canvas**: drag to pan, scroll/wheel to zoom, "Reset view" button
   restores the default framing. Legend (bottom-left) should list
   pad/track/via colors and the violation-marker glyph.
4. **Violation list**: click a violation card (or a marker on the canvas)
   and confirm the same violation highlights in both places. Severity
   badge color + text should match (critical/high/medium/low/info).
5. **Diagnosis panel**: after selecting a violation, confirm it shows: What
   happened, Root cause (with a confidence %), Engineering impact (bullet
   list), Recommended fix (checklist), Severity (deterministic vs.
   LLM-assessed side-by-side), Evidence (numbered citations with
   `drc`/`pcb`/`kb` source tags), an evidence-validation banner (pass/fail),
   human-review flag, and an observability trace (model, latency, tokens,
   prompt version).
6. **Upload flow**:
   - Click "Analyze your own .kicad_pcb" and pick a non-`.kicad_pcb` file
     (e.g. a `.txt`) -- expect an immediate, specific client-side error
     ("...doesn't look like a KiCad PCB file...") with **no** network
     request (check the Network tab: nothing fires).
   - Upload a real file, e.g. `data\demo\sample_board.kicad_pcb` -- expect
     it to parse and render the board. Violation count will be **0** and
     the status badge will read "DRC unavailable" if KiCad isn't installed
     (expected -- the pipeline never fabricates violations without a real
     DRC engine or a supplied fixture).
7. **Scrolling**: resize the browser window shorter than the page content
   (or use DevTools device toolbar at e.g. 1280x600). Confirm the whole
   Board Explorer page scrolls as one unit via the outer scrollbar --
   same mechanism as every other tab (see 4.6). At a normal laptop height
   (900px+) everything should fit with no scrollbar at all.

### 4.2 Pipeline Architecture

Static/illustrative tab: Evidence Hierarchy (L1-L5 cards) and Pipeline
Stages diagram. Click through each pipeline-stage node and confirm its
detail panel updates. No API calls; should render instantly.

### 4.3 Knowledge Base

1. Confirm the summary strip shows real counts (12 documents / 294 chunks
   / 214 pages as of the current curated set).
2. Click one of the sample query chips (e.g. "switching regulator
   efficiency") or type your own query and click Search.
3. Confirm results show **real** part numbers/snippets from real datasheets
   (e.g. MIC26903, AP63200, LTC4412) -- not placeholder text.
4. Confirm the document grid lists all indexed datasheets grouped by their
   6 source projects (AcornRobotElectronics, CF-Chef, HadesFCS, Meshinger,
   OPNhydro-r2, PortalHardware).

### 4.4 Evaluation

1. If `results/ablation_results.json` exists (from a prior `pcb-ai
   evaluate` run), confirm the bar chart, radar chart, token-usage chart,
   and per-condition summary table all render with matching numbers.
2. If it doesn't exist yet, confirm a clear empty state is shown (not a
   blank page or console error) -- `GET /eval/summary` returns
   `{"available": false}` in that case, not an error.
3. Confirm the "demonstration-scale, not validated research-scale" caveat
   banner is visible (this dashboard shows n=4-per-condition ablation
   results honestly, not overstated).

### 4.5 Research Lineage

Confirm live counts are shown per project (components/nets from the
bundled `pcb_qa-4FEE` reference repo) and the "Shared foundation / This
system's extension" framing renders. This section is read-only/display-only
by design -- it must never claim to feed the DRC pipeline.

### 4.6 Cross-cutting checks (all tabs)

- **Scrolling**: every tab (Board Explorer, Pipeline, Knowledge Base,
  Evaluation, Research Lineage) uses the *same* single scroll mechanism --
  the `<main>` element in `App.tsx`. None of them lock to viewport height
  with internal nested scroll panes; if you ever see one tab behave
  differently from the others when content overflows, that's a regression.
- **Keyboard/accessibility smoke test**: `Tab` through the top nav and
  confirm each tab button is announced as `tab` with `aria-selected`; the
  layer toggle and sample switcher are announced as grouped controls
  (`role="group"`) with `aria-pressed` on the active option; the canvas SVG
  has a descriptive `aria-label` (board size + violation count); violation
  list buttons have a full accessible name (severity + rule type +
  message), not just visual text fragments.
- **No console errors**: open DevTools console while clicking through all
  5 tabs and both sample-board switches; only expected messages are
  Vite/React dev-mode notices, never uncaught exceptions.

## 5. Browser-based automated smoke test (optional)

If you have Playwright/browser-automation tooling available, a fast smoke
sequence that exercises most of section 4 programmatically:

1. Load `http://localhost:5173`, wait for the Small sample to auto-load.
2. Click through all 5 tabs, confirm each renders without a thrown
   `pageError` event.
3. Click `Medium`, then `Large` sample buttons; wait for each to finish
   (poll `GET /pcb/samples` for `cached: true`, or just wait ~4 minutes).
4. Click a few violations of different severities (including the Medium
   board's `CRITICAL` short-circuit) and confirm the diagnosis panel
   populates with non-empty Evidence and a "validation passed" banner.
5. Programmatically check for real scrolling rather than trusting a single
   wheel-event simulation: prefer asserting `element.scrollHeight >
   element.clientHeight` plus a keyboard `PageDown` (synthetic mouse-wheel
   events on nested scroll containers are known to be unreliable in some
   headless/CDP automation setups even when the underlying CSS is correct).

## 6. Known gaps / not yet automated

- **No component-level (rendered UI) test coverage yet**: Vitest +
  Testing Library (added -- see section 2) covers hooks and pure helpers,
  but no `.tsx` component (e.g. `BoardExplorer`, `PCBCanvas`,
  `ViolationList`, `DiagnosisPanel`) has a render-level test yet. Section
  4's manual/visual checklist is still the primary coverage for actual
  rendered UI, canvas interaction, and cross-tab layout consistency.
- **Client-side upload validation** (`frontend/src/hooks/useAnalysis.ts`,
  `validateBoardFile`) checks extension, non-empty, and a 20MB size cap --
  it is a fast first line of feedback, not a security boundary; the backend
  independently re-validates.
- **Live-LLM-provider tests are manual, not in CI** (see DEVELOPMENT.md) --
  they require network access and API credentials that shouldn't be
  assumed present in every environment.

## 7. Troubleshooting

- **Vite shows "Failed to resolve import" / "Failed to reload" after
  deleting+recreating a `.tsx` file**: Vite's dev-server file watcher can
  get confused by delete-then-recreate (vs. in-place edit). Fully stop and
  restart `npm run dev`.
- **A `/pcb/samples/{id}/analyze` or `/pcb/demo` request seems to hang
  other requests too** (e.g. `/health` stops responding): every route that
  calls into the LLM pipeline must go through `run_in_threadpool` in
  `src/pcb_ai/api/app.py` -- a regression here would block the whole
  single-threaded event loop. Confirm `/health` still responds instantly
  from a second terminal while a long diagnosis request is in flight.
- **Port collisions**: this environment has had unrelated services on
  `:8000` before; the documented dev port is `:8931` for the backend and
  Vite's default `:5173` for the frontend. Don't kill other unrelated
  processes to free a port -- just pick a different one and update
  `CORS_ALLOW_ORIGINS` / the frontend's Vite proxy target if needed. The
  Docker Compose stack uses `:8000` (backend) and `:8080` (frontend) --
  check `docker ps` for conflicts before `docker compose up` if those are
  already taken (e.g. by an unrelated `docker-compose.yml` in the same
  shared environment); override with `docker compose up -p <other-port>`
  style port mappings in a local override file if needed, rather than
  stopping someone else's containers.
- **`docker compose build` intermittently fails right after starting
  Docker Desktop**: if the daemon was just started, the very first build
  can fail mid-`pip install` with a generic error while the Docker Desktop
  Linux VM is still stabilizing. Simply retry the build once the engine has
  been up for a bit (`docker info` returning a full `Server:` section, not
  just `Client:`, confirms it's ready).
- **`GEMINI_API_KEY`/`GEMINI_MODEL`/`GEMINI_BASE_URL` (or `CAF_MODEL_*`)
  seem to ignore what's in `.env`**: `docker compose`'s `${VAR:-default}`
  substitution reads the **host shell's own environment variables ahead
  of the `.env` file** (same precedence pydantic-settings uses for the
  backend process itself, see DEVELOPMENT.md). If your shell happens to
  already have one of these names set (confirmed to happen in this
  project's own dev environment, purely coincidentally), it silently wins
  over `.env`. Check with `Get-ChildItem Env: | Where-Object Name -like
  "GEMINI*"` / `"CAF_MODEL*"` (PowerShell) and clear any stray ones with
  `Remove-Item Env:\VARNAME` for the current session before `docker
  compose up`.
