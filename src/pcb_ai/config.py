"""Centralized configuration (Phase 28).

All environment-driven configuration lives here so no module reaches into
`os.environ` directly. Loaded via pydantic-settings from `.env` (see
`.env.example` for the full list of supported variables).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- KiCad ---
    kicad_cli_path: str = "kicad-cli"
    kicad_drc_timeout_s: int = 120

    # --- LLM provider (OpenAI-compatible) ---
    caf_model_provider: str = "vllm"
    caf_model_base_url: str = ""
    caf_model_api_key: str = ""
    caf_model_analysis: str = "nemotron3-super-120b"
    caf_model_general: str = "nemotron3-super-120b"
    caf_model_fast: str = "fast-classify"

    # --- Gemini (alternative provider, selected via CAF_MODEL_PROVIDER=gemini) ---
    # Deliberately separate from CAF_MODEL_* above (rather than reusing
    # CAF_MODEL_BASE_URL/CAF_MODEL_API_KEY) so a teammate can add just these
    # two lines to test with their own free Gemini API key
    # (https://aistudio.google.com/apikey) without touching or clearing your
    # existing Nemotron/vLLM gateway configuration in the same .env file --
    # see pcb_ai.llm.factory for how CAF_MODEL_PROVIDER picks between them.
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_base_url: str = ""

    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_request_timeout_s: int = 180

    # --- Observability ---
    caf_langfuse_enabled: bool = False
    caf_langfuse_host: str = "http://localhost:13000"
    caf_langfuse_public_key: str = ""
    caf_langfuse_secret_key: str = ""

    # --- Retrieval / RAG ---
    knowledge_dir: str = "./data/knowledge"
    datasheet_dir: str = "./data/datasheets"
    retrieval_top_k: int = 6
    retrieval_similarity_threshold: float = 0.05
    chunk_size_tokens: int = 350
    chunk_overlap_tokens: int = 60

    # --- Severity ---
    severity_policy_version: str = "1.0"

    # --- Context limits ---
    max_pcb_context_objects: int = 40
    max_knowledge_chunks: int = 8

    # --- Logging ---
    log_level: str = "INFO"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Frontend / demo / research-reference data (relative to cwd, which
    # should be the repo root when running `uvicorn`/`pcb-ai`) ---
    demo_dir: str = "./data/demo"
    samples_dir: str = "./data/samples"
    results_dir: str = "./results"
    pcb_qa_reference_dir: str = "./pcb_qa-4FEE"

    @property
    def general_model(self) -> str:
        return self.caf_model_general or self.caf_model_analysis

    @property
    def knowledge_path(self) -> Path:
        return Path(self.knowledge_dir)

    @property
    def datasheet_path(self) -> Path:
        return Path(self.datasheet_dir)

    @property
    def demo_path(self) -> Path:
        return Path(self.demo_dir)

    @property
    def samples_path(self) -> Path:
        return Path(self.samples_dir)

    @property
    def results_path(self) -> Path:
        return Path(self.results_dir)

    @property
    def pcb_qa_reference_path(self) -> Path:
        return Path(self.pcb_qa_reference_dir)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
