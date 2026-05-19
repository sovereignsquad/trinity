from __future__ import annotations

import json
from pathlib import Path

import pytest
from trinity_core.adapters.model import ModelInventoryError, load_model_inventory


def test_load_model_inventory_returns_empty_inventory_when_manifest_missing(
    tmp_path: Path,
) -> None:
    models_root = tmp_path / "models"
    inventory = load_model_inventory(
        env={"TRINITY_MODELS_ROOT": str(models_root)},
        repo_root=Path("/Users/Shared/Projects/trinity"),
    )

    assert inventory.loaded is False
    assert inventory.entries == ()
    assert inventory.manifest_path == models_root / "manifests" / "trinity-model-manifest.json"


def test_load_model_inventory_normalizes_relative_paths_and_provider_refs(
    tmp_path: Path,
) -> None:
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    model_file = models_root / "llms" / "chat" / "granite-4.0-h-350m-4bit" / "model.safetensors"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    model_file.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "trinity-model-inventory.v1",
                "entries": [
                    {
                        "model_id": "granite-4.0-h-350m-4bit",
                        "family": "granite",
                        "capability": "chat",
                        "format": "mlx",
                        "local_path": "llms/chat/granite-4.0-h-350m-4bit/model.safetensors",
                        "provider_modes": ["direct", "ollama"],
                        "provider_refs": {"ollama": "granite4:350m"},
                        "quantization": "4bit",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    inventory = load_model_inventory(
        env={"TRINITY_MODELS_ROOT": str(models_root)},
        repo_root=Path("/Users/Shared/Projects/trinity"),
    )

    assert inventory.loaded is True
    assert inventory.manifest_version == "trinity-model-inventory.v1"
    assert len(inventory.entries) == 1
    entry = inventory.entries[0]
    assert entry.local_path == model_file.resolve()
    assert entry.provider_refs["ollama"] == "granite4:350m"
    assert inventory.find_by_model_id("granite-4.0-h-350m-4bit") == entry
    assert inventory.find_for_route(
        provider="ollama",
        route_model="granite4:350m",
    ) == entry


def test_load_model_inventory_rejects_repo_local_models_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    models_root = repo_root / "models"

    with pytest.raises(ModelInventoryError, match="models root must live outside"):
        load_model_inventory(
            env={"TRINITY_MODELS_ROOT": str(models_root)},
            repo_root=repo_root,
        )


def test_load_model_inventory_rejects_entry_path_outside_models_root(tmp_path: Path) -> None:
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    outside_file = tmp_path / "outside.gguf"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    outside_file.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "trinity-model-inventory.v1",
                "entries": [
                    {
                        "model_id": "bad-model",
                        "family": "bad",
                        "capability": "chat",
                        "format": "gguf",
                        "local_path": str(outside_file),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelInventoryError, match="must stay within the shared models root"):
        load_model_inventory(
            env={"TRINITY_MODELS_ROOT": str(models_root)},
            repo_root=Path("/Users/Shared/Projects/trinity"),
        )
