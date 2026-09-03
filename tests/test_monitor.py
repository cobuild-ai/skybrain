import pytest
from skybrain.core.monitor import (
    HostMemoryMonitor,
    HostMemoryInfo,
    MemoryStatusLevel,
    SystemGuard,
    BackgroundMemoryWatcher,
)


class TestHostMemoryMonitor:
    def test_get_memory_info_returns_valid_metrics(self):
        mem = HostMemoryMonitor.get_memory_info()
        assert isinstance(mem, HostMemoryInfo)
        assert mem.total_gb > 0.0
        assert mem.available_gb >= 0.0
        assert mem.used_gb >= 0.0
        assert 0.0 <= mem.percent_used <= 100.0
        assert mem.status in (MemoryStatusLevel.SAFE, MemoryStatusLevel.WARNING, MemoryStatusLevel.CRITICAL)

        d = mem.to_dict()
        assert "total_gb" in d
        assert "available_gb" in d
        assert "percent_used" in d
        assert "status" in d


class TestSystemGuard:
    def test_safe_memory_evaluation(self, monkeypatch):
        fake_mem = HostMemoryInfo(
            total_gb=16.0,
            available_gb=8.0,
            used_gb=8.0,
            percent_used=50.0,
            status=MemoryStatusLevel.SAFE,
            os_name="Darwin",
        )
        monkeypatch.setattr(HostMemoryMonitor, "get_memory_info", classmethod(lambda cls: fake_mem))

        assessment = SystemGuard.evaluate(has_cloud_fallback=False)
        assert assessment.allowed is True
        assert assessment.fallback_to_cloud is False
        assert "Memory Safe" in assessment.message

    def test_warning_memory_evaluation(self, monkeypatch):
        fake_mem = HostMemoryInfo(
            total_gb=16.0,
            available_gb=3.0,
            used_gb=13.0,
            percent_used=81.2,
            status=MemoryStatusLevel.WARNING,
            os_name="Darwin",
        )
        monkeypatch.setattr(HostMemoryMonitor, "get_memory_info", classmethod(lambda cls: fake_mem))

        assessment = SystemGuard.evaluate(has_cloud_fallback=False)
        assert assessment.allowed is True
        assert assessment.fallback_to_cloud is False
        assert "Memory Warning" in assessment.message

    def test_critical_memory_with_cloud_fallback(self, monkeypatch):
        fake_mem = HostMemoryInfo(
            total_gb=16.0,
            available_gb=1.8,
            used_gb=14.2,
            percent_used=88.7,
            status=MemoryStatusLevel.CRITICAL,
            os_name="Darwin",
        )
        monkeypatch.setattr(HostMemoryMonitor, "get_memory_info", classmethod(lambda cls: fake_mem))

        assessment = SystemGuard.evaluate(has_cloud_fallback=True)
        assert assessment.allowed is True
        assert assessment.fallback_to_cloud is True
        assert "Safely offloading" in assessment.message

    def test_critical_memory_without_cloud_fallback_blocks(self, monkeypatch):
        fake_mem = HostMemoryInfo(
            total_gb=16.0,
            available_gb=1.8,
            used_gb=14.2,
            percent_used=88.7,
            status=MemoryStatusLevel.CRITICAL,
            os_name="Darwin",
        )
        monkeypatch.setattr(HostMemoryMonitor, "get_memory_info", classmethod(lambda cls: fake_mem))

        assessment = SystemGuard.evaluate(has_cloud_fallback=False)
        assert assessment.allowed is False
        assert assessment.fallback_to_cloud is False
        assert "Memory Guard Block" in assessment.message


class TestBackgroundMemoryWatcher:
    def test_start_stop_watcher(self):
        watcher = BackgroundMemoryWatcher(interval_seconds=0.1)
        watcher.start()
        assert watcher._thread is not None and watcher._thread.is_alive()
        watcher.stop()
        assert watcher._thread is None
