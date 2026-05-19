from __future__ import annotations

from pathlib import Path

from trinity_core.model_config import (
    DEFAULT_TRINITY_EVALUATOR_MODEL,
    DEFAULT_TRINITY_GENERATOR_MODEL,
    DEFAULT_TRINITY_REFINER_MODEL,
    load_reply_model_config,
)


def test_model_config_defaults_from_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("TRINITY_GENERATOR_MODEL", raising=False)
    monkeypatch.delenv("TRINITY_REFINER_MODEL", raising=False)
    monkeypatch.delenv("TRINITY_EVALUATOR_MODEL", raising=False)

    config = load_reply_model_config()

    assert config.generator.model == DEFAULT_TRINITY_GENERATOR_MODEL
    assert config.refiner.model == DEFAULT_TRINITY_REFINER_MODEL
    assert config.evaluator.model == DEFAULT_TRINITY_EVALUATOR_MODEL


def test_model_config_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("TRINITY_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("TRINITY_GENERATOR_MODEL", "tiny-model")
    monkeypatch.setenv("TRINITY_REFINER_MODEL", "writer-model")
    monkeypatch.setenv("TRINITY_EVALUATOR_MODEL", "judge-model")
    monkeypatch.setenv("TRINITY_OLLAMA_BASE_URL", "http://127.0.0.1:11435")

    config = load_reply_model_config()

    assert config.provider == "ollama"
    assert config.ollama_base_url == "http://127.0.0.1:11435"
    assert config.generator.model == "tiny-model"
    assert config.refiner.model == "writer-model"
    assert config.evaluator.model == "judge-model"


def test_model_config_mistral_cli_env_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setenv("TRINITY_MODEL_PROVIDER", "mistral-cli")
    monkeypatch.setenv("TRINITY_MISTRAL_CLI_EXECUTABLE", "/opt/mistral/bin/vibe")
    monkeypatch.setenv("TRINITY_MISTRAL_CLI_ARGS", "--agent auto-approve --output json")
    monkeypatch.setenv("TRINITY_MISTRAL_CLI_MODE", "vibe")
    monkeypatch.setenv("TRINITY_MISTRAL_CLI_MODEL_BINDING", "advisory")

    config = load_reply_model_config()

    assert config.provider == "mistral-cli"
    assert config.mistral_cli_executable == "/opt/mistral/bin/vibe"
    assert config.mistral_cli_args == ("--agent", "auto-approve", "--output", "json")
    assert config.mistral_cli_mode == "vibe"
    assert config.mistral_cli_model_binding == "advisory"


def test_model_config_derives_model_id_from_shared_inventory(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        """
{
  "manifest_version": "trinity-model-inventory.v1",
  "entries": [
    {
      "model_id": "granite-4.0-h-350m-4bit",
      "family": "granite",
      "capability": "chat",
      "format": "mlx",
      "local_path": "llms/chat/granite/model.safetensors",
      "provider_refs": {
        "deterministic": "granite4:350m"
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRINITY_MODELS_ROOT", str(models_root))

    config = load_reply_model_config()

    assert config.generator.model_id == "granite-4.0-h-350m-4bit"
    assert config.refiner.model_id is None
    assert config.evaluator.model_id is None


def test_model_config_loads_nested_role_fields_from_persisted_file(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(config_path))
    config_path.write_text(
        """
{
  "provider": "ollama",
  "ollama_base_url": "http://127.0.0.1:11434",
  "timeout_seconds": 30.0,
  "generator": {
    "provider": "ollama",
    "model": "granite4:350m",
    "model_id": "granite-shared",
    "temperature": 0.25,
    "keep_alive": "10m"
  },
  "refiner": {
    "provider": "ollama",
    "model": "mistral:latest",
    "model_id": "mistral-shared",
    "temperature": 0.35,
    "keep_alive": "10m"
  },
  "evaluator": {
    "provider": "ollama",
    "model": "qwen2.5:7b",
    "model_id": "qwen-shared",
    "temperature": 0.1,
    "keep_alive": "10m"
  }
}
""".strip(),
        encoding="utf-8",
    )

    config = load_reply_model_config()

    assert config.provider == "ollama"
    assert config.generator.model == "granite4:350m"
    assert config.generator.model_id == "granite-shared"
    assert config.refiner.model_id == "mistral-shared"
    assert config.evaluator.model_id == "qwen-shared"
