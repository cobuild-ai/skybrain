import pytest
from pathlib import Path
from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS, DEFAULT_PRESET_KEY


def test_catalog_paths_and_defaults(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    # 1. Defaults
    assert catalog.get_active_key() == DEFAULT_PRESET_KEY
    assert not catalog.is_installed()

    # 2. List presets
    presets = catalog.list_models()
    assert len(presets) >= 2
    keys = [p["key"] for p in presets]
    assert "gemma-4-e4b" in keys
    assert "gemma-2-2b" in keys

    # 3. Switch active key
    catalog.set_active_key("gemma-2-2b")
    assert catalog.get_active_key() == "gemma-2-2b"


def test_catalog_installed_check(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    path = catalog.get_model_path("gemma-4-e4b")
    with open(path, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    assert catalog.is_installed("gemma-4-e4b")



def test_ensure_model_ready_when_installed(tmp_path):
    models_dir = tmp_path / "models"
    home_dir = tmp_path / "home"
    catalog = ModelCatalog(models_dir=models_dir, home_dir=home_dir)

    path = catalog.get_model_path("gemma-4-e4b")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.seek(101 * 1024 * 1024 - 1)
        f.write(b"\0")

    result_path = catalog.ensure_model_ready("gemma-4-e4b")
    assert result_path == path
    assert catalog.is_installed("gemma-4-e4b")

