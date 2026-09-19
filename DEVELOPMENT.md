# Development

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env
# edit .env with your LLM provider credentials
```

## Environment variables

See `.env.example` for the full list (KiCad path/timeout, LLM provider/
model/temperature/max-tokens/timeout, optional Langfuse tracing, RAG
directories/top_k/threshold/chunk sizing, severity policy version, context
limits, logging, API host/port). All are read through
`pcb_ai.config.Settings` (pydantic-settings) -- no module reads
`os.environ` directly.

## Running tests

```powershell
.venv\Scripts\python -m pytest tests\ -v
```

46 tests covering: the KiCad parser (including a coordinate-transform
regression test), DRC normalization/taxonomy, the PCB context graph and
retriever, the RAG chunker/retriever, the severity policy, evidence
validation (including fabricated-reference and fabricated-citation
cases), the diagnosis pipeline's failure handling (invalid JSON, schema
violation, provider error -- all via a deterministic `MockLLMProvider`, no
network calls), the report generator, the agent tool registry, and one
full end-to-end pipeline test. All 46 pass without network access.

Tests that exercise the **live** LLM endpoint (used during development to
validate the OpenAI-compatible adapter, JSON mode, and tool-calling
against the configured `nemotron3-super-120b` gateway) were run manually
and are not part of the automated suite, since they require network
access and API credentials that should not be assumed present in CI.

## KiCad availability

This environment has **no KiCad installation**. `pcb_ai.drc.runner`:
- searches `KICAD_CLI_PATH` then `PATH` for `kicad-cli`;
- if not found, `run_kicad_drc(...)` returns `executed=False` with a clear
  `error` string -- it never invents violations;
- `load_fixture_drc_report(path, pcb)` loads a pre-recorded, real-schema
  DRC JSON report (see `tests/fixtures/sample_drc_report.json`, hand-built
  to match the documented `kicad-cli pcb drc --format json` schema from
  KiCad's own `RC_JSON` serializer) for fully offline development/testing,
  and marks the result `fixture_used=True` so it is never confused with a
  live run in reports or evaluation output.

To validate against **real** KiCad DRC output:
1. Install KiCad 7+ (`kicad-cli` must be on `PATH`, or set
   `KICAD_CLI_PATH`).
2. Run `pcb-ai drc <board.kicad_pcb>` (no `--fixture-drc`) and compare the
   normalized violations against KiCad's own DRC panel.
3. If any new KiCad violation `type` string doesn't appear in
   `KICAD_RULE_ID_TAXONOMY_MAP` (`src/pcb_ai/schemas/drc.py`), it will
   correctly fall back to `ViolationTaxonomy.OTHER` (never silently
   dropped) -- consider adding the mapping.

## LLM provider

Configured via `CAF_MODEL_PROVIDER`/`CAF_MODEL_BASE_URL`/
`CAF_MODEL_API_KEY`/`CAF_MODEL_ANALYSIS`. `CAF_MODEL_PROVIDER=mock` uses
`MockLLMProvider` (no network) for fully offline runs. The configured
`nemotron3-super-120b` model is a **reasoning model**: it emits
`reasoning_content` before the final `content`, which consumes completion
tokens. `LLM_MAX_TOKENS` defaults to 4096 to leave headroom for reasoning
+ a full structured JSON diagnosis; if you see `insufficient_evidence:
LLM returned invalid JSON` with a truncation-looking error, raise
`LLM_MAX_TOKENS` further.

### Testing with a Gemini API key instead

`CAF_MODEL_PROVIDER=gemini` is a built-in alternative for anyone who wants
to try the whole project with their own **free** Gemini API key instead of
this project's Nemotron gateway -- no code changes needed. It works
because Google publishes an official OpenAI-wire-format-compatible
endpoint for Gemini (`https://ai.google.dev/gemini-api/docs/openai`), and
`OpenAICompatibleProvider` (`src/pcb_ai/llm/openai_compatible.py`) already
speaks that exact wire format to the Nemotron gateway -- Gemini needed no
new provider class, just different `base_url`/`model`/`api_key` values.

It uses **dedicated** `GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_BASE_URL`
settings (not `CAF_MODEL_*`) specifically so both configs can live in the
same `.env` without one clobbering the other:

```powershell
# In .env: get a free key at https://aistudio.google.com/apikey, then:
CAF_MODEL_PROVIDER=gemini
GEMINI_API_KEY=<your key>
# GEMINI_MODEL and GEMINI_BASE_URL are optional -- see pcb_ai.llm.factory
# for the current default model/endpoint if left unset.
```

`GEMINI_DEFAULT_MODEL` (`gemini-2.5-flash-lite` as of this writing) was
chosen specifically for its generous **free-tier** daily quota -- live
testing found the newer flagship `gemini-3.6-flash` capped at just 20
requests/day on a free key, which a single sample board's worth of
diagnoses can exceed on its own. If you're using a **paid/billed** Gemini
key, quota isn't a practical concern and you can set `GEMINI_MODEL` to a
more capable model (e.g. a `-pro` tier) for potentially higher-quality
diagnoses; the pipeline itself doesn't care which Gemini model you pick.

Switching `CAF_MODEL_PROVIDER` back to `vllm` (or whatever it was) later
restores the Nemotron config exactly as it was -- see
`tests/test_llm_factory.py` for the coexistence guarantee this relies on.

One gotcha to know about: pydantic-settings resolves config in the order
**OS environment variables > `.env` file > code defaults**. If
`GEMINI_MODEL`/`GEMINI_API_KEY`/`GEMINI_BASE_URL` happen to already be set
as real OS environment variables on your machine (e.g. from another tool
that uses the same conventional names), they'll take precedence over
whatever you put in `.env`. Check with `Get-ChildItem Env: | Where-Object
Name -like "GEMINI*"` (PowerShell) if Gemini behaves unexpectedly.

## Adding a new LLM provider

Implement `BaseLLMProvider` (`src/pcb_ai/llm/base.py`): one method,
`complete(messages, *, tools, json_mode, temperature, max_tokens, model)
-> LLMResponse`. Register it in `pcb_ai.llm.factory.get_llm_provider`. Note
that most OpenAI-wire-format-compatible services (OpenAI itself, vLLM/
LiteLLM proxies, and -- as of this project -- Gemini via its own
compatibility endpoint) don't need a new class at all, just a new
`provider_kind` branch in the factory that supplies the right
`base_url`/`model`/`api_key` to the existing `OpenAICompatibleProvider`.

## Adding a new knowledge backend

`KnowledgeRetriever` is a concrete class, not an ABC, but its public
surface (`index_document`, `index_file`, `index_directory`, `search`,
`search_by_component`, `search_by_violation_type`, `get_source`, `save`,
`load`) is what `AgentToolbox` and `ViolationDiagnosisAgent` depend on. To
swap in a real vector database, implement the same methods against
FAISS/Chroma/Qdrant/pgvector and pass an instance wherever
`KnowledgeRetriever()` is currently constructed (`AnalysisService`, CLI
commands, `eval/runner.py`).

## Linting / type-checking

No linter/type-checker was configured in the original (empty) workspace,
so none was added speculatively, per the instruction to only run tools
that already exist. `pytest` is the only configured/required check; add
`ruff`/`mypy` explicitly if you want them going forward.
