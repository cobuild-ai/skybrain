import fcntl
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx

from skybrain.core.config import settings

logger = logging.getLogger("skybrain.supervisor")

PID_FILE = settings.home_dir / "skybrain.pid"
LOG_FILE = settings.home_dir / "skybrain.log"
LOCK_FILE = settings.home_dir / "skybrain.lock"

_lock_file_handle = None


class DaemonSupervisor:
    """Controls the background SkyBrain API server daemon process with robust single-instance locking and cleanup."""

    @staticmethod
    def acquire_instance_lock() -> bool:
        """Acquires an exclusive OS-level file lock using fcntl.flock to guarantee single-instance execution."""
        global _lock_file_handle
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            _lock_file_handle = open(LOCK_FILE, "w")
            fcntl.flock(_lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_file_handle.write(str(os.getpid()))
            _lock_file_handle.flush()
            return True
        except (IOError, BlockingIOError, PermissionError):
            return False

    @staticmethod
    def release_instance_lock() -> None:
        """Releases the instance lock file."""
        global _lock_file_handle
        if _lock_file_handle:
            try:
                fcntl.flock(_lock_file_handle, fcntl.LOCK_UN)
                _lock_file_handle.close()
            except Exception:
                pass
            _lock_file_handle = None
        LOCK_FILE.unlink(missing_ok=True)

    @staticmethod
    def get_pid() -> Optional[int]:
        """Gets PID of the running SkyBrain daemon process via PID file or port listener."""
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)
                return pid
            except (ValueError, OSError):
                PID_FILE.unlink(missing_ok=True)

        # Fallback: check port listener (e.g. when managed by launchd or subshell)
        try:
            res = subprocess.run(
                ["lsof", "-t", f"-i:{settings.port}"],
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if res.returncode == 0 and res.stdout.strip():
                pids = [int(p) for p in res.stdout.strip().splitlines() if p.strip().isdigit()]
                if pids:
                    return pids[0]
        except Exception:
            pass
        return None

    @staticmethod
    def is_running() -> bool:
        """Checks if SkyBrain daemon is actively serving."""
        return DaemonSupervisor.get_pid() is not None or DaemonSupervisor.check_health() is not None

    @staticmethod
    def check_health(host: str = settings.host, port: int = settings.port, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """Probes the /healthz endpoint."""
        url = f"http://{host}:{port}/healthz"
        try:
            resp = httpx.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    @staticmethod
    def kill_stale_daemon_processes(port: Optional[int] = settings.port, match_patterns: Optional[List[str]] = None) -> int:
        """Standardized orphan/zombie process cleanup matching MySkyNet lifecycle patterns."""
        return DaemonSupervisor.cleanup_stale_processes(port=port, match_patterns=match_patterns)

    @staticmethod
    def check_health_fast(host: str = settings.host, port: int = settings.port, timeout: float = 0.15) -> bool:
        """Ultra-fast 150ms health check ping for zero-latency pre-flight verification."""
        url = f"http://{host}:{port}/healthz"
        try:
            resp = httpx.get(url, timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def ensure_daemon_alive(host: str = settings.host, port: int = settings.port, max_wait: float = 3.0) -> bool:
        """Guarantees SkyBrain daemon is alive; auto-heals if dead or hanging."""
        if DaemonSupervisor.check_health_fast(host=host, port=port):
            return True

        logger.warning("🩺 Daemon unresponsive during pre-flight check. Triggering auto-heal...")
        DaemonSupervisor.kill_stale_daemon_processes(port=port)
        DaemonSupervisor.start(host=host, port=port, force=True)

        start_time = time.time()
        while time.time() - start_time < max_wait:
            time.sleep(0.2)
            if DaemonSupervisor.check_health_fast(host=host, port=port):
                logger.info("✅ SkyBrain daemon auto-healed and serving.")
                return True

        return False

    @staticmethod
    def cleanup_stale_processes(port: Optional[int] = settings.port, match_patterns: Optional[List[str]] = None) -> int:
        """
        Scans and terminates any stale, orphan, or zombie processes holding the port or running skybrain.
        Uses psutil if available, with lsof and ps aux fallback.
        """
        current_pid = os.getpid()
        patterns = [p.lower() for p in (match_patterns or ["skybrain.server.app", "skybrain.server"])]
        killed_pids = set()

        # 1. Kill by port listener (lsof)
        if port:
            try:
                res = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True, timeout=2.0)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().splitlines():
                        if line.strip().isdigit():
                            pid = int(line.strip())
                            if pid != current_pid:
                                killed_pids.add(pid)
            except Exception:
                pass

        # 2. Kill by process name / cmdline inspection
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    cmdline = " ".join(proc.info['cmdline'] or []).lower()
                    if any(pat in cmdline for pat in patterns):
                        killed_pids.add(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            try:
                out = subprocess.check_output("ps aux | grep -i 'skybrain.server' | grep -v grep", shell=True, text=True, stderr=subprocess.DEVNULL)
                for line in out.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) > 1 and parts[1].isdigit():
                        pid = int(parts[1])
                        if pid != current_pid:
                            killed_pids.add(pid)
            except Exception:
                pass

        # 3. Graceful termination (SIGTERM -> sleep -> SIGKILL)
        for pid in list(killed_pids):
            try:
                logger.info(f"🧹 [SkyBrain Cleanup] Terminating stale process (PID={pid})...")
                os.kill(pid, signal.SIGTERM)
            except OSError:
                killed_pids.discard(pid)

        if killed_pids:
            time.sleep(0.5)
            for pid in killed_pids:
                try:
                    os.kill(pid, 0)
                    logger.warning(f"⚠️ [SkyBrain Cleanup] Process {pid} still alive, sending SIGKILL...")
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

        PID_FILE.unlink(missing_ok=True)
        return len(killed_pids)

    @staticmethod
    def start(host: str = settings.host, port: int = settings.port, force: bool = False) -> bool:
        """Starts the SkyBrain daemon process in the background with auto-cleanup."""
        if DaemonSupervisor.is_running():
            if not force:
                logger.info("SkyBrain daemon is already active.")
                return True
            logger.info("Force restart requested. Cleaning up stale daemon...")
            DaemonSupervisor.stop()
            DaemonSupervisor.cleanup_stale_processes(port=port)

        # Cleanup port before binding to prevent [Errno 48]
        DaemonSupervisor.cleanup_stale_processes(port=port)

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "skybrain.server.app:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "info"
        ]

        with open(LOG_FILE, "a", encoding="utf-8") as log_out:
            proc = subprocess.Popen(
                cmd,
                stdout=log_out,
                stderr=log_out,
                start_new_session=True
            )

        PID_FILE.write_text(str(proc.pid), encoding="utf-8")

        # Wait up to 5s for server to start
        for _ in range(25):
            time.sleep(0.2)
            if DaemonSupervisor.check_health(host, port):
                logger.info(f"✅ SkyBrain daemon started successfully (PID: {proc.pid})")
                return True

        return DaemonSupervisor.is_running()

    @staticmethod
    def stop() -> bool:
        """Stops the running SkyBrain daemon safely."""
        pid = DaemonSupervisor.get_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                for _ in range(20):
                    time.sleep(0.2)
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        PID_FILE.unlink(missing_ok=True)
                        break
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

        DaemonSupervisor.cleanup_stale_processes(port=settings.port)
        PID_FILE.unlink(missing_ok=True)
        return True

    @staticmethod
    def restart(host: str = settings.host, port: int = settings.port) -> bool:
        """Performs a clean shutdown and restart of the SkyBrain daemon."""
        logger.info("🔄 Restarting SkyBrain daemon...")
        DaemonSupervisor.stop()
        time.sleep(0.5)
        return DaemonSupervisor.start(host=host, port=port, force=True)
