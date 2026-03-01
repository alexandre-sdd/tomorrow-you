from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MistralChatRuntimeConfig(BaseModel):
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    timeout_seconds: float
    endpoint: str


class PromptComposerRuntimeConfig(BaseModel):
    max_memory_facts: int
    max_memory_notes: int
    max_history_turns: int


class ProfileSummaryLimits(BaseModel):
    core_values: int
    fears: int
    hidden_tensions: int


class ContextResolverRuntimeConfig(BaseModel):
    profile_summary_limits: ProfileSummaryLimits


class FutureGenerationRuntimeConfig(BaseModel):
    default_count: int
    allowed_counts: list[int]
    default_time_horizon: str
    default_time_horizons_by_depth: dict[int, str]
    mood_fallback_chains: dict[str, list[str]]

    @model_validator(mode="after")
    def _validate_counts(self) -> FutureGenerationRuntimeConfig:
        if not self.allowed_counts:
            raise ValueError("future_generation.allowed_counts must not be empty")
        if self.default_count not in self.allowed_counts:
            raise ValueError("future_generation.default_count must be present in allowed_counts")
        return self


class FutureGenContextRuntimeConfig(BaseModel):
    max_conversation_excerpts_per_ancestor: int
    max_total_excerpts: int


class CliRuntimeConfig(BaseModel):
    storage_root: str
    branch_default_count: int = Field(ge=1)


class AppRuntimeConfig(BaseModel):
    mistral_model: str
    avatar_provider: str


class ServerRuntimeConfig(BaseModel):
    host: str
    port: int
    cors_origins: list[str]


class StorageRuntimeConfig(BaseModel):
    path: str


class RuntimeConfig(BaseModel):
    mistral_chat: MistralChatRuntimeConfig
    prompt_composer: PromptComposerRuntimeConfig
    context_resolver: ContextResolverRuntimeConfig
    future_generation: FutureGenerationRuntimeConfig
    future_generation_context: FutureGenContextRuntimeConfig
    cli: CliRuntimeConfig
    app: AppRuntimeConfig
    server: ServerRuntimeConfig
    storage: StorageRuntimeConfig

    @model_validator(mode="after")
    def _validate_cli_branch_default(self) -> RuntimeConfig:
        if self.cli.branch_default_count not in self.future_generation.allowed_counts:
            raise ValueError(
                "cli.branch_default_count must be one of future_generation.allowed_counts"
            )
        return self


_runtime_config: RuntimeConfig | None = None


def get_runtime_config() -> RuntimeConfig:
    global _runtime_config
    if _runtime_config is None:
        _runtime_config = _load_runtime_config()
    return _runtime_config


def _load_runtime_config() -> RuntimeConfig:
    configured_path = os.getenv("RUNTIME_CONFIG_PATH", "").strip()
    runtime_path = (
        Path(configured_path)
        if configured_path
        else _default_runtime_path()
    )
    raw = _load_runtime_file(runtime_path)

    # Convert JSON object keys (always strings) to int keys for depth map.
    fg = raw.get("future_generation", {})
    depth_map = fg.get("default_time_horizons_by_depth", {})
    if isinstance(depth_map, dict):
        fg["default_time_horizons_by_depth"] = {
            int(k): v for k, v in depth_map.items()
        }
        raw["future_generation"] = fg

    return RuntimeConfig.model_validate(raw)


def _default_runtime_path() -> Path:
    base = Path(__file__).resolve()
    yaml_path = base.with_name("runtime.yaml")
    if yaml_path.exists():
        return yaml_path

    json_path = base.with_name("runtime.json")
    if json_path.exists():
        return json_path

    raise FileNotFoundError(
        "Runtime config file not found: expected backend/config/runtime.yaml or runtime.json"
    )


def _load_runtime_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Runtime config file not found: {path}")

    suffix = path.suffix.lower()

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "PyYAML is required to load YAML runtime config files. "
                "Install it with: pip install pyyaml"
            ) from exc
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raise ValueError(
            f"Unsupported runtime config extension '{path.suffix}'. Use .yaml/.yml or .json"
        )

    if not isinstance(raw, dict):
        raise ValueError(f"Runtime config root must be an object in: {path}")

    return raw
