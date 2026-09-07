"""Tests for config/watcher.py"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class FakeEvent:
    """Fake watchdog FileModifiedEvent."""

    def __init__(self, src_path: str, is_directory: bool = False):
        self.src_path = src_path
        self.is_directory = is_directory


class TestConfigFileHandlerInit:
    def test_init_default_cooldown(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        assert h.callback is cb
        assert h.cooldown_seconds == 1.0
        assert h._last_reload == 0.0
        assert h._lock is not None

    def test_init_custom_cooldown(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb, cooldown_seconds=5.0)
        assert h.cooldown_seconds == 5.0


class TestConfigFileHandlerOnModified:
    def test_ignores_directory_events(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/path", is_directory=True))
        cb.assert_not_called()

    def test_ignores_unrelated_files(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/random.txt"))
        cb.assert_not_called()
        h.on_modified(FakeEvent("/some/README.md"))
        cb.assert_not_called()

    def test_ignores_hidden_files(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/.config.yaml"))
        cb.assert_not_called()

    def test_triggers_callback_on_config_yaml(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_called_once()

    def test_triggers_callback_on_config_yml(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/config.yml"))
        cb.assert_called_once()

    def test_triggers_callback_on_pii_patterns_yaml(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb)
        h.on_modified(FakeEvent("/some/pii_patterns.yaml"))
        cb.assert_called_once()

    def test_cooldown_skips_second_rapid_event(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb, cooldown_seconds=2.0)

        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_called_once()
        cb.reset_mock()

        # Immediate second event — should be debounced
        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_not_called()

    def test_cooldown_allows_event_after_cooldown(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock()
        h = ConfigFileHandler(cb, cooldown_seconds=0.05)

        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_called_once()

        # Wait for cooldown to expire
        time.sleep(0.06)

        cb.reset_mock()
        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_called_once()

    def test_callback_exception_is_swallowed(self):
        from config.watcher import ConfigFileHandler

        cb = MagicMock(side_effect=RuntimeError("reload boom"))
        h = ConfigFileHandler(cb)
        # Must not raise
        h.on_modified(FakeEvent("/some/config.yaml"))
        cb.assert_called_once()


class TestConfigWatcherInit:
    def test_init_sets_attributes(self):
        from config.watcher import ConfigWatcher

        config_path = Path("/etc/app/config.yaml")
        cb = MagicMock()
        w = ConfigWatcher(config_path, cb, cooldown_seconds=3.0)

        assert w.config_path == config_path
        assert w.callback is cb
        assert w.cooldown_seconds == 3.0
        assert w._observer is None
        assert w._handler is None


class TestConfigWatcherStart:
    def test_start_twice_is_noop(self):
        from config.watcher import ConfigWatcher

        cb = MagicMock()
        w = ConfigWatcher(Path("/etc/app/config.yaml"), cb)

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = True

        w._observer = fake_observer

        with patch("config.watcher.Observer", return_value=fake_observer):
            w.start()

        # Observer.start() should not have been called again
        fake_observer.start.assert_not_called()

    def test_start_creates_observer_and_starts(self):
        from config.watcher import ConfigWatcher

        cb = MagicMock()
        w = ConfigWatcher(Path("/etc/app/config.yaml"), cb)

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = False

        with patch("config.watcher.Observer", return_value=fake_observer) as mock_observer_cls:
            w.start()

        mock_observer_cls.assert_called_once()
        fake_observer.schedule.assert_called_once()
        fake_observer.start.assert_called_once()
        assert w._handler is not None

    def test_start_schedules_handler_on_parent_dir(self):
        from config.watcher import ConfigWatcher

        cb = MagicMock()
        config_path = Path("/etc/app/config.yaml")
        w = ConfigWatcher(config_path, cb)

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = False

        with patch("config.watcher.Observer", return_value=fake_observer):
            w.start()

        # schedule called with (handler, parent_dir, recursive=False)
        call_args = fake_observer.schedule.call_args
        assert call_args[0][1] == "/etc/app"
        assert call_args[1]["recursive"] is False


class TestConfigWatcherStop:
    def test_stop_does_nothing_when_not_started(self):
        from config.watcher import ConfigWatcher

        cb = MagicMock()
        w = ConfigWatcher(Path("/etc/app/config.yaml"), cb)
        w.stop()  # must not raise
        assert w._observer is None

    def test_stop_calls_observer_stop_and_join(self):
        from config.watcher import ConfigWatcher

        cb = MagicMock()
        w = ConfigWatcher(Path("/etc/app/config.yaml"), cb)

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = True

        w._observer = fake_observer
        w.stop()

        fake_observer.stop.assert_called_once()
        fake_observer.join.assert_called_once()
        assert w._observer is None


class TestConfigWatcherIsRunning:
    def test_is_running_false_when_no_observer(self):
        from config.watcher import ConfigWatcher

        w = ConfigWatcher(Path("/etc/app/config.yaml"), MagicMock())
        assert w.is_running() is False

    def test_is_running_true_when_observer_alive(self):
        from config.watcher import ConfigWatcher

        w = ConfigWatcher(Path("/etc/app/config.yaml"), MagicMock())

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = True
        w._observer = fake_observer

        assert w.is_running() is True

    def test_is_running_false_when_observer_dead(self):
        from config.watcher import ConfigWatcher

        w = ConfigWatcher(Path("/etc/app/config.yaml"), MagicMock())

        fake_observer = MagicMock()
        fake_observer.is_alive.return_value = False
        w._observer = fake_observer

        assert w.is_running() is False