import pytest
from skybrain.server.supervisor import DaemonSupervisor


def test_kill_stale_daemon_processes_executes_cleanly():
    # Calling kill_stale_daemon_processes on non-existent or dummy port
    count = DaemonSupervisor.kill_stale_daemon_processes(port=59999, match_patterns=["non_existent_skybrain_proc"])
    assert isinstance(count, int)
    assert count >= 0


def test_check_health_fast_unreachable():
    # Fast check on unused port should return False without long hang
    alive = DaemonSupervisor.check_health_fast(host="127.0.0.1", port=59999, timeout=0.05)
    assert alive is False


def test_ensure_daemon_alive_when_healthy(monkeypatch):
    monkeypatch.setattr(DaemonSupervisor, "check_health_fast", staticmethod(lambda **kwargs: True))
    assert DaemonSupervisor.ensure_daemon_alive() is True
