"""Real-time Host Memory Monitor and Pre-flight System Guard for SkyBrain.

Protects the host machine (macOS Unified Memory & Linux) from out-of-memory (OOM)
freezes and degraded SLM performance by monitoring available memory in real time.
"""

from dataclasses import dataclass
from enum import Enum
import logging
import os
from pathlib import Path
import platform
import subprocess
import threading
import time
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("skybrain.monitor")


class MemoryStatusLevel(str, Enum):
    SAFE = "SAFE"          # Available >= 3.5 GB: Optimal condition for on-device SLM
    WARNING = "WARNING"    # 2.5 GB <= Available < 3.5 GB: Approaching swap, caution advised
    CRITICAL = "CRITICAL"  # Available < 2.5 GB: High risk of swap thrashing and OS freeze


@dataclass
class HostMemoryInfo:
    total_gb: float
    available_gb: float
    used_gb: float
    percent_used: float
    status: MemoryStatusLevel
    os_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_gb": round(self.total_gb, 2),
            "available_gb": round(self.available_gb, 2),
            "used_gb": round(self.used_gb, 2),
            "percent_used": round(self.percent_used, 1),
            "status": self.status.value,
            "os_name": self.os_name,
        }


@dataclass
class PreflightAssessment:
    allowed: bool
    status: MemoryStatusLevel
    available_gb: float
    recommended_gb: float = 3.0
    fallback_to_cloud: bool = False
    message: str = ""


class HostMemoryMonitor:
    """Zero-dependency cross-platform host memory monitor targeting macOS Unified Memory."""

    SAFE_THRESHOLD_GB: float = 3.5
    CRITICAL_THRESHOLD_GB: float = 2.5

    @classmethod
    def get_memory_info(cls) -> HostMemoryInfo:
        """Retrieves real-time physical memory metrics from OS."""
        sys_platform = platform.system().lower()

        total_bytes: int = 0
        avail_bytes: int = 0

        if sys_platform == "darwin":
            total_bytes, avail_bytes = cls._get_macos_memory()
        elif sys_platform == "linux":
            total_bytes, avail_bytes = cls._get_linux_memory()
        else:
            total_bytes, avail_bytes = cls._get_generic_memory()

        total_gb = max(total_bytes / (1024 ** 3), 0.1)
        avail_gb = max(avail_bytes / (1024 ** 3), 0.0)
        used_gb = max(total_gb - avail_gb, 0.0)
        percent_used = min(max((used_gb / total_gb) * 100.0, 0.0), 100.0)

        if avail_gb >= cls.SAFE_THRESHOLD_GB:
            status = MemoryStatusLevel.SAFE
        elif avail_gb >= cls.CRITICAL_THRESHOLD_GB:
            status = MemoryStatusLevel.WARNING
        else:
            status = MemoryStatusLevel.CRITICAL

        return HostMemoryInfo(
            total_gb=total_gb,
            available_gb=avail_gb,
            used_gb=used_gb,
            percent_used=percent_used,
            status=status,
            os_name=platform.system(),
        )

    @classmethod
    def _get_macos_memory(cls) -> tuple[int, int]:
        """Calculates total and available RAM on macOS via sysctl and vm_stat."""
        total_bytes = 0
        try:
            total_out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=1.5).decode().strip()
            total_bytes = int(total_out)
        except Exception:
            total_bytes = 16 * (1024 ** 3)

        avail_bytes = 0
        try:
            vm_out = subprocess.check_output(["vm_stat"], timeout=1.5).decode()
            stats = {}
            for line in vm_out.splitlines():
                if ":" in line:
                    parts = line.split(":")
                    key = parts[0].strip()
                    val = parts[1].strip().rstrip(".")
                    try:
                        stats[key] = int(val)
                    except ValueError:
                        pass

            page_size = 4096
            try:
                ps_out = subprocess.check_output(["pagesize"], timeout=1.0).decode().strip()
                page_size = int(ps_out)
            except Exception:
                pass

            free_pages = stats.get("Pages free", 0)
            inactive_pages = stats.get("Pages inactive", 0)
            speculative_pages = stats.get("Pages speculative", 0)
            avail_bytes = (free_pages + inactive_pages + speculative_pages) * page_size
        except Exception:
            avail_bytes = int(total_bytes * 0.3)

        return total_bytes, avail_bytes

    @classmethod
    def _get_linux_memory(cls) -> tuple[int, int]:
        """Calculates total and available RAM on Linux via /proc/meminfo."""
        total_bytes = 0
        avail_bytes = 0
        try:
            meminfo = Path("/proc/meminfo").read_text()
            data = {}
            for line in meminfo.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    val_kb = v.strip().split()[0]
                    data[k.strip()] = int(val_kb) * 1024
            total_bytes = data.get("MemTotal", 0)
            avail_bytes = data.get("MemAvailable", data.get("MemFree", 0))
        except Exception:
            total_bytes = 16 * (1024 ** 3)
            avail_bytes = int(total_bytes * 0.4)
        return total_bytes, avail_bytes

    @classmethod
    def _get_generic_memory(cls) -> tuple[int, int]:
        total = 16 * (1024 ** 3)
        return total, int(total * 0.5)


class SystemGuard:
    """Pre-flight memory protection guard to ensure safe on-device LLM inference."""

    @staticmethod
    def evaluate(has_cloud_fallback: bool = False) -> PreflightAssessment:
        """Evaluates current memory safety before executing heavy local model inference."""
        mem = HostMemoryMonitor.get_memory_info()

        if mem.status == MemoryStatusLevel.SAFE:
            return PreflightAssessment(
                allowed=True,
                status=mem.status,
                available_gb=mem.available_gb,
                fallback_to_cloud=False,
                message=f"✅ Memory Safe ({mem.available_gb:.1f} GB available)",
            )

        if mem.status == MemoryStatusLevel.WARNING:
            logger.warning(
                f"⚠️ [Memory Guard] Low host memory: {mem.available_gb:.1f} GB available. Recommended ≥ 3.0 GB."
            )
            return PreflightAssessment(
                allowed=True,
                status=mem.status,
                available_gb=mem.available_gb,
                fallback_to_cloud=False,
                message=f"⚠️ Memory Warning ({mem.available_gb:.1f} GB available). Performance may swap.",
            )

        # CRITICAL (< 2.5 GB available)
        if has_cloud_fallback:
            logger.warning(
                f"🚨 [Memory Guard] Host memory CRITICAL ({mem.available_gb:.1f} GB). Offloading to Cloud LLM to protect OS!"
            )
            return PreflightAssessment(
                allowed=True,
                status=mem.status,
                available_gb=mem.available_gb,
                fallback_to_cloud=True,
                message=(
                    f"⚠️ Host available RAM is low ({mem.available_gb:.1f} GB < 2.5 GB). "
                    "Safely offloading inference to Cloud LLM to prevent OS freeze."
                ),
            )
        else:
            logger.error(
                f"🛑 [Memory Guard] Host memory CRITICAL ({mem.available_gb:.1f} GB) and NO cloud key found. Blocking local execution."
            )
            return PreflightAssessment(
                allowed=False,
                status=mem.status,
                available_gb=mem.available_gb,
                fallback_to_cloud=False,
                message=(
                    f"🚨 [Memory Guard Block] Host available RAM is critically low ({mem.available_gb:.1f} GB / Recommended ≥ 3.0 GB).\n"
                    "To prevent macOS lockup and OOM freeze, local SLM execution is suspended.\n"
                    "👉 Solution: Free up browser tabs/applications or configure GEMINI_API_KEY for --cloud mode."
                ),
            )


class BackgroundMemoryWatcher:
    """Periodic background memory watcher thread that alerts when memory enters critical states."""

    def __init__(self, interval_seconds: float = 15.0, alert_callback: Optional[Callable[[HostMemoryInfo], None]] = None):
        self.interval = interval_seconds
        self.alert_callback = alert_callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_status: Optional[MemoryStatusLevel] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SkyBrainMemoryWatcher")
        self._thread.start()
        logger.info("📡 [Memory Watcher] Background memory monitor started (interval=%.1fs)", self.interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("🛑 [Memory Watcher] Background memory monitor stopped")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                mem = HostMemoryMonitor.get_memory_info()
                if mem.status == MemoryStatusLevel.CRITICAL and self._last_status != MemoryStatusLevel.CRITICAL:
                    logger.critical(
                        f"🚨 [HOST MEMORY CRITICAL ALERT] Available RAM: {mem.available_gb:.2f} GB ({mem.percent_used:.1f}% used). System freeze risk!"
                    )
                    if self.alert_callback:
                        self.alert_callback(mem)
                elif mem.status == MemoryStatusLevel.WARNING and self._last_status == MemoryStatusLevel.SAFE:
                    logger.warning(
                        f"⚠️ [HOST MEMORY WARNING] Available RAM: {mem.available_gb:.2f} GB. Approaching swap limit."
                    )
                self._last_status = mem.status
            except Exception as e:
                logger.debug(f"Memory watch loop error: {e}")
            self._stop_event.wait(self.interval)
