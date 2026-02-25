"""Configuration loader — YAML + env overrides + path resolution."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class PathsConfig(BaseModel):
    taxonomy_file: Path
    dgccrf_corpus_dir: Path
    particuliers_corpus_dir: Path
    entreprises_corpus_dir: Path
    inc_corpus_dir: Path
    output_dir: Path
    chroma_db_path: Path
    prompts_dir: Path
    fiches_dir: Path


class IncCleaningConfig(BaseModel):
    min_content_length: int = 200
    skip_directories: list[str] = []
    boilerplate_markers: list[str] = []
    boilerplate_threshold: int = 4


class EmbeddingsConfig(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: str = "intfloat/multilingual-e5-small"
    dimension: int = 384


class ChunkingConfig(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 100
    min_chunk_length: int = 50


class RetrievalConfig(BaseModel):
    collection_name: str = "dgccrf_corpus"
    top_k: int = 20
    min_score: float = 0.3
    max_source_chars: int = 15000
    dgccrf_weight: float = 1.5


class LLMConfig(BaseModel):
    endpoint: str = "https://albert.api.etalab.gouv.fr/v1"
    api_key: str = ""
    model: str = "openweight-medium"
    temperature: float = 0.3
    max_tokens_situation: int = 4000
    max_tokens_sous_domaine: int = 6000
    max_tokens_domaine: int = 5000
    timeout: int = 120
    rate_limit_rpm: int = 30
    retry_count: int = 3
    retry_delay: int = 5


class RewriteConfig(BaseModel):
    model: str = "openai/gpt-oss-120b"
    temperature: float = 0.3
    max_tokens_situation: int = 8000
    max_tokens_sous_domaine: int = 10000
    max_tokens_domaine: int = 8000
    max_source_chars: int = 40000
    top_k_per_query: int = 10
    sujets_proches_top_k: int = 5
    sujets_proches_min_score: float = 0.55
    faux_amis_similarity_range: list[float] = [0.45, 0.80]
    faux_amis_top_k: int = 3
    timeout: int = 240
    rate_limit_rpm: int = 20


class AppConfig(BaseModel):
    paths: PathsConfig
    inc_cleaning: IncCleaningConfig = IncCleaningConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    llm: LLMConfig = LLMConfig()
    rewrite: RewriteConfig = RewriteConfig()


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load config.yaml, resolve paths relative to config dir, apply env overrides."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config_path = Path(config_path).resolve()
    config_dir = config_path.parent

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    # Resolve relative paths against config directory
    paths_raw = raw.get("paths", {})
    for key, val in paths_raw.items():
        p = Path(val)
        if not p.is_absolute():
            paths_raw[key] = str((config_dir / p).resolve())

    # Apply env overrides for LLM config
    llm_raw = raw.get("llm", {})
    llm_raw["api_key"] = os.environ.get("LLM_API_KEY", llm_raw.get("api_key", ""))
    if os.environ.get("LLM_ENDPOINT"):
        llm_raw["endpoint"] = os.environ["LLM_ENDPOINT"]
    if os.environ.get("LLM_MODEL"):
        llm_raw["model"] = os.environ["LLM_MODEL"]
    if os.environ.get("LLM_TEMPERATURE"):
        llm_raw["temperature"] = float(os.environ["LLM_TEMPERATURE"])

    return AppConfig(**raw)
