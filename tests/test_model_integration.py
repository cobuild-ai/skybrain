import pytest
from skybrain.core.hardware import HardwareAutoTuner, HardwareInfo, EnvironmentTier
from skybrain.engine.model_catalog import MODEL_PRESETS, ModelCatalog


class TestModelIntegrationDiagnostics:
    def test_model_suitability_mapping(self):
        catalog = ModelCatalog()
        presets = catalog.list_models()
        assert len(presets) > 0

        for p in presets:
            env = HardwareAutoTuner.assess_environment(model_key=p["key"])
            assert env.tier in (
                EnvironmentTier.ABUNDANT,
                EnvironmentTier.OPTIMAL,
                EnvironmentTier.CONSTRAINED,
                EnvironmentTier.INCOMPATIBLE,
            )
            assert isinstance(env.recommended_layers, int)

    def test_incompatible_model_blocking(self):
        # Simulate very low RAM (1.0 GB available)
        hw_low = HardwareInfo(
            os_name="Darwin",
            architecture="arm64",
            is_64bit=True,
            cpu_count=8,
            gpu_backend="metal",
            gpu_name="Apple Silicon Metal GPU (arm64)",
            total_ram_gb=8.0,
            available_ram_gb=1.0,  # Below 2.0GB
            total_vram_gb=8.0,
            free_vram_gb=1.0,
        )
        assessment = HardwareAutoTuner.assess_environment(model_key="qwen3.8", hw=hw_low)
        assert assessment.tier == EnvironmentTier.INCOMPATIBLE
        assert assessment.allowed is False
        assert "동작 불가" in assessment.title
