import pytest
from skybrain.core.hardware import (
    HardwareAutoTuner,
    HardwareInfo,
    EnvironmentAssessment,
    EnvironmentTier,
)
from skybrain.core.config import settings


class TestHardwareAutoTuner:
    def test_detect_hardware_live_system(self):
        hw = HardwareAutoTuner.detect_hardware()
        assert isinstance(hw, HardwareInfo)
        assert hw.os_name in ("Darwin", "Linux", "Windows")
        assert hw.cpu_count > 0
        assert hw.total_ram_gb > 0.0
        assert hw.available_ram_gb >= 0.0
        assert hw.gpu_backend in ("metal", "cuda", "rocm", "cpu")
        assert len(hw.gpu_name) > 0

    def test_tier4_abundant_metal(self):
        hw = HardwareInfo(
            os_name="Darwin",
            architecture="arm64",
            is_64bit=True,
            cpu_count=10,
            gpu_backend="metal",
            gpu_name="Apple Silicon Metal GPU (arm64)",
            total_ram_gb=32.0,
            available_ram_gb=16.0,
            total_vram_gb=32.0,
            free_vram_gb=16.0,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.ABUNDANT
        assert assessment.allowed is True
        assert assessment.recommended_layers == -1
        assert "여유 충분" in assessment.title

    def test_tier3_optimal_metal(self):
        hw = HardwareInfo(
            os_name="Darwin",
            architecture="arm64",
            is_64bit=True,
            cpu_count=8,
            gpu_backend="metal",
            gpu_name="Apple Silicon Metal GPU (arm64)",
            total_ram_gb=16.0,
            available_ram_gb=5.0,
            total_vram_gb=16.0,
            free_vram_gb=5.0,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.OPTIMAL
        assert assessment.allowed is True
        assert assessment.recommended_layers == -1
        assert "원활한 동작" in assessment.title

    def test_tier1_constrained_cpu_only(self):
        hw = HardwareInfo(
            os_name="Linux",
            architecture="x86_64",
            is_64bit=True,
            cpu_count=4,
            gpu_backend="cpu",
            gpu_name="CPU Only (No Acceleration)",
            total_ram_gb=16.0,
            available_ram_gb=4.0,
            total_vram_gb=None,
            free_vram_gb=None,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.CONSTRAINED
        assert assessment.allowed is True
        assert assessment.recommended_layers == 0
        assert "부하 가능" in assessment.title
        assert "CPU Fallback" in assessment.details.get("reasons", [""])[0]

    def test_tier1_constrained_low_vram_cuda(self):
        hw = HardwareInfo(
            os_name="Linux",
            architecture="x86_64",
            is_64bit=True,
            cpu_count=8,
            gpu_backend="cuda",
            gpu_name="NVIDIA GeForce GTX 1650",
            total_ram_gb=16.0,
            available_ram_gb=6.0,
            total_vram_gb=4.0,
            free_vram_gb=1.8,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.CONSTRAINED
        assert assessment.allowed is True
        # Partial layer offload expected
        assert 0 < assessment.recommended_layers < 36
        assert "부하 가능" in assessment.title

    def test_tier2_incompatible_insufficient_ram(self):
        hw = HardwareInfo(
            os_name="Darwin",
            architecture="arm64",
            is_64bit=True,
            cpu_count=8,
            gpu_backend="metal",
            gpu_name="Apple Silicon Metal GPU (arm64)",
            total_ram_gb=8.0,
            available_ram_gb=1.2,  # < 2.0GB
            total_vram_gb=8.0,
            free_vram_gb=1.2,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.INCOMPATIBLE
        assert assessment.allowed is False
        assert assessment.recommended_layers == 0
        assert "동작 불가" in assessment.title
        assert "치명적인 가용 메모리" in assessment.title

    def test_tier2_incompatible_32bit(self):
        hw = HardwareInfo(
            os_name="Linux",
            architecture="i686",
            is_64bit=False,
            cpu_count=4,
            gpu_backend="cpu",
            gpu_name="CPU Only",
            total_ram_gb=4.0,
            available_ram_gb=3.0,
            total_vram_gb=None,
            free_vram_gb=None,
        )
        assessment = HardwareAutoTuner.assess_environment(hw=hw)
        assert assessment.tier == EnvironmentTier.INCOMPATIBLE
        assert assessment.allowed is False
        assert "32비트" in assessment.title

    def test_resolve_gpu_layers_cuda_scaling(self):
        # 8GB Free VRAM: Full offload
        hw_high = HardwareInfo(
            os_name="Linux", architecture="x86_64", is_64bit=True, cpu_count=8,
            gpu_backend="cuda", gpu_name="NVIDIA RTX 3080", total_ram_gb=32.0,
            available_ram_gb=16.0, total_vram_gb=10.0, free_vram_gb=8.0
        )
        assert HardwareAutoTuner.resolve_gpu_layers(hw=hw_high) == -1

        # Very low VRAM (< 1GB): Fall back to CPU
        hw_low = HardwareInfo(
            os_name="Linux", architecture="x86_64", is_64bit=True, cpu_count=8,
            gpu_backend="cuda", gpu_name="NVIDIA GTX 1050", total_ram_gb=16.0,
            available_ram_gb=8.0, total_vram_gb=2.0, free_vram_gb=0.6
        )
        assert HardwareAutoTuner.resolve_gpu_layers(hw=hw_low) == 0

    def test_config_gpu_layers_resolution(self):
        # Test default auto resolution
        layers = settings.get_resolved_gpu_layers()
        assert isinstance(layers, int)

        # Test manual override
        settings.n_gpu_layers = 18
        assert settings.get_resolved_gpu_layers() == 18

        # Restore auto
        settings.n_gpu_layers = "auto"
        assert settings.get_resolved_gpu_layers() in (-1, 0) or settings.get_resolved_gpu_layers() > 0
