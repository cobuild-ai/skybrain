"""Hardware Auto-Tuning and 4-Tier Pre-Flight Environment Diagnostic Module for SkyBrain.

Detects host CPU/GPU/VRAM/RAM architecture and automatically computes the optimal
`n_gpu_layers` setting, while classifying the deployment environment into 4 distinct tiers:
  1. CONSTRAINED (부하 발생 가능: CPU Fallback 또는 저용량 VRAM/RAM)
  2. INCOMPATIBLE (동작 불가: 가용 RAM < 2.0GB 등 치명적 자원 부족)
  3. OPTIMAL (원활한 동작: 적정 RAM/VRAM 및 GPU 가속)
  4. ABUNDANT (여유 충분: 8GB+ RAM 및 고성능 Metal/CUDA 풀가속)
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Optional, Dict, Any

from skybrain.core.monitor import HostMemoryMonitor, HostMemoryInfo

logger = logging.getLogger("skybrain.hardware")


class EnvironmentTier(str, Enum):
    """4-Tier classification for host execution environment capability."""
    CONSTRAINED = "CONSTRAINED"    # 1. 부하가 생길 수 있지만 동작은 가능한 경우
    INCOMPATIBLE = "INCOMPATIBLE"  # 2. 동작 자체가 불가능 할 정도로 부족한 성능 환경인 경우
    OPTIMAL = "OPTIMAL"            # 3. 원활한 동작 환경인 경우
    ABUNDANT = "ABUNDANT"          # 4. 여유가 충분한 환경인 경우


@dataclass
class HardwareInfo:
    """Detected hardware profile of the host machine."""
    os_name: str
    architecture: str
    is_64bit: bool
    cpu_count: int
    gpu_backend: str  # "metal", "cuda", "rocm", "cpu"
    gpu_name: str
    total_ram_gb: float
    available_ram_gb: float
    total_vram_gb: Optional[float] = None
    free_vram_gb: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "os_name": self.os_name,
            "architecture": self.architecture,
            "is_64bit": self.is_64bit,
            "cpu_count": self.cpu_count,
            "gpu_backend": self.gpu_backend,
            "gpu_name": self.gpu_name,
            "total_ram_gb": round(self.total_ram_gb, 2),
            "available_ram_gb": round(self.available_ram_gb, 2),
            "total_vram_gb": round(self.total_vram_gb, 2) if self.total_vram_gb is not None else None,
            "free_vram_gb": round(self.free_vram_gb, 2) if self.free_vram_gb is not None else None,
        }


@dataclass
class EnvironmentAssessment:
    """Assessment result of host environment capability with recommendations."""
    tier: EnvironmentTier
    allowed: bool
    title: str
    message: str
    recommended_layers: int
    hardware: HardwareInfo
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "allowed": self.allowed,
            "title": self.title,
            "message": self.message,
            "recommended_layers": self.recommended_layers,
            "hardware": self.hardware.to_dict(),
            "details": self.details,
        }


class HardwareAutoTuner:
    """Detects system hardware and auto-tunes GPU offload layers and pre-flight health."""

    MIN_RAM_REQUIRED_GB: float = 2.0     # RAM less than 2.0GB cannot safely load SLM
    OPTIMAL_RAM_GB: float = 3.5          # Minimum RAM for optimal execution
    ABUNDANT_RAM_GB: float = 8.0         # RAM for abundant high-throughput execution

    # Estimated model specs (layers, weights in GB, KV cache overhead in GB)
    MODEL_LAYER_SPECS: Dict[str, Dict[str, Any]] = {
        "gemma-4-e4b": {"layers": 36, "weight_gb": 2.8, "kv_gb": 0.8},
        "qwen-2.5-3b": {"layers": 36, "weight_gb": 2.0, "kv_gb": 0.5},
        "gemma-2-2b": {"layers": 26, "weight_gb": 1.6, "kv_gb": 0.3},
        "default": {"layers": 36, "weight_gb": 2.2, "kv_gb": 0.6},
    }

    @classmethod
    def detect_hardware(cls) -> HardwareInfo:
        """Inspects OS, CPU, RAM, and GPU devices."""
        sys_os = platform.system()
        arch = platform.machine().lower()
        is_64bit = platform.architecture()[0] == "64bit"
        cpu_count = os.cpu_count() or 4

        mem: HostMemoryInfo = HostMemoryMonitor.get_memory_info()
        total_ram = mem.total_gb
        avail_ram = mem.available_gb

        gpu_backend = "cpu"
        gpu_name = "CPU Only (No Acceleration)"
        total_vram: Optional[float] = None
        free_vram: Optional[float] = None

        # 1. macOS Apple Silicon Metal check
        if sys_os == "Darwin" and arch in ("arm64", "aarch64"):
            gpu_backend = "metal"
            gpu_name = f"Apple Silicon Metal GPU ({arch})"
            # Apple Silicon has Unified Memory, so VRAM is shared with host RAM
            total_vram = total_ram
            free_vram = avail_ram

        # 2. NVIDIA CUDA check via nvidia-smi
        elif shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.total,memory.free,name", "--format=csv,noheader,nounits"],
                    timeout=2.0
                ).decode().strip()
                lines = out.splitlines()
                if lines:
                    parts = [p.strip() for p in lines[0].split(",")]
                    if len(parts) >= 3:
                        tot_mb = float(parts[0])
                        free_mb = float(parts[1])
                        card_name = parts[2]
                        gpu_backend = "cuda"
                        gpu_name = f"NVIDIA {card_name}"
                        total_vram = tot_mb / 1024.0
                        free_vram = free_mb / 1024.0
            except Exception as e:
                logger.debug(f"nvidia-smi query failed: {e}")

        # 3. AMD ROCm check via rocm-smi if cuda not found
        if gpu_backend == "cpu" and shutil.which("rocm-smi"):
            gpu_backend = "rocm"
            gpu_name = "AMD ROCm GPU"

        return HardwareInfo(
            os_name=sys_os,
            architecture=arch,
            is_64bit=is_64bit,
            cpu_count=cpu_count,
            gpu_backend=gpu_backend,
            gpu_name=gpu_name,
            total_ram_gb=total_ram,
            available_ram_gb=avail_ram,
            total_vram_gb=total_vram,
            free_vram_gb=free_vram,
        )

    @classmethod
    def resolve_gpu_layers(cls, model_key: str = "default", hw: Optional[HardwareInfo] = None) -> int:
        """Calculates optimal n_gpu_layers (-1 for full, N for partial, 0 for CPU)."""
        if hw is None:
            hw = cls.detect_hardware()

        spec = cls.MODEL_LAYER_SPECS.get(model_key, cls.MODEL_LAYER_SPECS["default"])
        total_layers = spec["layers"]
        weight_gb = spec["weight_gb"]
        kv_gb = spec["kv_gb"]

        # CPU Fallback
        if hw.gpu_backend == "cpu":
            return 0

        # Apple Silicon Metal
        if hw.gpu_backend == "metal":
            if hw.available_ram_gb >= cls.OPTIMAL_RAM_GB:
                return -1  # Full GPU offload
            elif hw.available_ram_gb >= cls.MIN_RAM_REQUIRED_GB:
                # Scaled offload to prevent high memory pressure
                fraction = max(0.2, (hw.available_ram_gb - 1.5) / 2.0)
                return max(1, min(total_layers, int(total_layers * fraction)))
            else:
                return 0

        # NVIDIA CUDA
        if hw.gpu_backend == "cuda" and hw.free_vram_gb is not None:
            needed_vram = weight_gb + kv_gb
            if hw.free_vram_gb >= needed_vram:
                return -1  # Full GPU offload
            elif hw.free_vram_gb >= 1.0:
                # Partial layer offload calculation
                layer_mb = (weight_gb * 1024.0) / total_layers
                safe_vram_mb = max(0.0, (hw.free_vram_gb - 0.4) * 1024.0 * 0.85)
                offloaded = int(safe_vram_mb / layer_mb)
                return max(0, min(total_layers, offloaded))
            else:
                return 0  # Not enough VRAM, fall back to host CPU

        # Default fallback
        return 0

    @classmethod
    def assess_environment(cls, model_key: str = "default", hw: Optional[HardwareInfo] = None) -> EnvironmentAssessment:
        """Evaluates host system and assigns one of 4 environment capability tiers."""
        if hw is None:
            hw = cls.detect_hardware()

        rec_layers = cls.resolve_gpu_layers(model_key=model_key, hw=hw)

        # ─────────────────────────────────────────────────────────────────
        # Tier 2: INCOMPATIBLE (동작 자체가 불가능 할 정도로 부족한 성능 환경)
        # ─────────────────────────────────────────────────────────────────
        if not hw.is_64bit:
            return EnvironmentAssessment(
                tier=EnvironmentTier.INCOMPATIBLE,
                allowed=False,
                title="🛑 [Tier 2: 동작 불가] 32비트 아키텍처 비호환",
                message=(
                    f"SkyBrain과 SLM 엔진은 64비트 OS를 필수로 요구합니다. (현재: {hw.architecture} 32-bit)\n"
                    "👉 64비트 운영체제 환경에서 다시 실행해 주십시오."
                ),
                recommended_layers=0,
                hardware=hw,
                details={"reason": "non_64bit_os"},
            )

        if hw.available_ram_gb < cls.MIN_RAM_REQUIRED_GB:
            return EnvironmentAssessment(
                tier=EnvironmentTier.INCOMPATIBLE,
                allowed=False,
                title="🛑 [Tier 2: 동작 불가] 치명적인 가용 메모리(RAM) 부족",
                message=(
                    f"현재 가용 RAM이 {hw.available_ram_gb:.1f} GB로, 모델 최소 실행 요구량({cls.MIN_RAM_REQUIRED_GB:.1f} GB)에 미달합니다.\n"
                    "이 상태로 구동할 경우 OS 동결(Kernel Panic) 및 프로세스 강제 종료(OOM Killer)가 발생합니다.\n"
                    "👉 실행 중인 다른 무거운 앱(브라우저 탭, Docker 등)을 종료하여 최소 2.5GB 이상의 RAM을 확보해 주십시오."
                ),
                recommended_layers=0,
                hardware=hw,
                details={"reason": "insufficient_ram", "available_ram_gb": hw.available_ram_gb},
            )

        # ─────────────────────────────────────────────────────────────────
        # Tier 4: ABUNDANT (여유가 충분한 최적 성능 환경)
        # ─────────────────────────────────────────────────────────────────
        is_abundant_metal = (
            hw.gpu_backend == "metal" and hw.available_ram_gb >= cls.ABUNDANT_RAM_GB
        )
        is_abundant_cuda = (
            hw.gpu_backend == "cuda"
            and (hw.free_vram_gb or 0.0) >= 8.0
            and hw.available_ram_gb >= cls.OPTIMAL_RAM_GB
        )
        is_abundant_cpu = (
            hw.gpu_backend == "cpu"
            and hw.cpu_count >= 16
            and hw.available_ram_gb >= 16.0
        )

        if is_abundant_metal or is_abundant_cuda or is_abundant_cpu:
            return EnvironmentAssessment(
                tier=EnvironmentTier.ABUNDANT,
                allowed=True,
                title="🚀 [Tier 4: 여유 충분] 최상급 하드웨어 및 넉넉한 가속 자원",
                message=(
                    f"가용 메모리({hw.available_ram_gb:.1f} GB) 및 가속 장치({hw.gpu_name})가 매우 여유롭습니다.\n"
                    f"대규모 컨텍스트(16k~128k)와 초고속 GPU 풀가속(레이어: {rec_layers})이 완벽히 지원됩니다."
                ),
                recommended_layers=rec_layers,
                hardware=hw,
                details={"status": "excellent_headroom"},
            )

        # ─────────────────────────────────────────────────────────────────
        # Tier 3: OPTIMAL (원활한 동작 환경)
        # ─────────────────────────────────────────────────────────────────
        is_optimal_metal = (
            hw.gpu_backend == "metal" and hw.available_ram_gb >= cls.OPTIMAL_RAM_GB
        )
        is_optimal_cuda = (
            hw.gpu_backend == "cuda"
            and (hw.free_vram_gb or 0.0) >= 3.0
            and hw.available_ram_gb >= cls.OPTIMAL_RAM_GB
        )
        is_optimal_cpu = (
            hw.gpu_backend == "cpu"
            and hw.cpu_count >= 8
            and hw.available_ram_gb >= 6.0
        )

        if is_optimal_metal or is_optimal_cuda or is_optimal_cpu:
            return EnvironmentAssessment(
                tier=EnvironmentTier.OPTIMAL,
                allowed=True,
                title="🟢 [Tier 3: 원활한 동작] 안정적인 온디바이스 SLM 구동 환경",
                message=(
                    f"가용 RAM {hw.available_ram_gb:.1f} GB 및 {hw.gpu_name} 기반으로 "
                    f"온디바이스 AI 추론 및 백그라운드 서빙이 쾌적하고 원활하게 동작합니다. (할당 레이어: {rec_layers})"
                ),
                recommended_layers=rec_layers,
                hardware=hw,
                details={"status": "optimal_ready"},
            )

        # ─────────────────────────────────────────────────────────────────
        # Tier 1: CONSTRAINED (부하가 생길 수 있지만 동작은 가능한 경우)
        # ─────────────────────────────────────────────────────────────────
        reasons = []
        if hw.gpu_backend == "cpu":
            reasons.append("GPU 가속기 미감지 (CPU Fallback 모드 실행)")
        elif hw.gpu_backend == "cuda" and (hw.free_vram_gb or 0.0) < 3.0:
            reasons.append(f"VRAM 용량 제한 ({hw.free_vram_gb:.1f} GB 가용 ➔ 부분 레이어 오프로드: {rec_layers}개)")
        if hw.available_ram_gb < cls.OPTIMAL_RAM_GB:
            reasons.append(f"가용 RAM 주의 상태 ({hw.available_ram_gb:.1f} GB 가용 / 권장 3.5GB 이상)")

        reason_str = " & ".join(reasons) if reasons else "자원 한계 감지"

        return EnvironmentAssessment(
            tier=EnvironmentTier.CONSTRAINED,
            allowed=True,
            title="⚠️ [Tier 1: 부하 가능] 자원 제약 환경 감지 (동작은 가능)",
            message=(
                f"SkyBrain 동작은 가능하나, 다음 요인으로 인해 응답 지연(Latency) 또는 발열/부하가 발생할 수 있습니다:\n"
                f"• 감지 요인: {reason_str}\n"
                f"• 계산된 GPU 레이어: {rec_layers} (CPU/GPU 분할)\n"
                f"👉 고부하 작업 시 Cloud LLM 연동 또는 가용 메모리 확보를 권장합니다."
            ),
            recommended_layers=rec_layers,
            hardware=hw,
            details={"reasons": reasons, "cpu_fallback": hw.gpu_backend == "cpu"},
        )
