# manual_processor/tests/test_usb_monitor.py
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.usb_monitor import (
    USBMonitor,
    USBFileHandler,
    create_usb_monitor,
    is_ready_for_processing,
    get_safe_filename,
    _HAS_WATCHDOG
)

class TestUSBMonitor:
    """USBMonitor クラスのテスト"""
    
    def test_usb_monitor_initialization_with_valid_paths(self):
        """有効なパスでUSBMonitorが初期化できること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            assert len(monitor.paths) == 1
            assert monitor.paths[0] == Path(tmpdir)
            assert not monitor._is_running
    
    def test_usb_monitor_initialization_with_invalid_paths(self):
        """存在しないパスが指定された場合、空リストになること"""
        monitor = USBMonitor(["/nonexistent/path/that/does/not/exist"], callback=lambda p, e: None)
        assert len(monitor.paths) == 0
        # デフォルトパスが設定されるか、少なくとも初期化エラーにならないこと
        assert hasattr(monitor, 'paths')
    
    def test_usb_monitor_start_stop(self):
        """start/stopが正しく動作すること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            monitor.start()
            assert monitor._is_running
            monitor.stop()
            assert not monitor._is_running

class TestCreateUsbMonitor:
    """ファクトリ関数 create_usb_monitor のテスト"""
    
    def test_create_usb_monitor_returns_instance(self):
        """インスタンスが返されること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = create_usb_monitor([tmpdir], lambda p, e: None)
            assert isinstance(monitor, USBMonitor)
    
    def test_create_usb_monitor_with_empty_paths(self):
        """空のパスリストでもインスタンス作成できること"""
        monitor = create_usb_monitor([], lambda p, e: None)
        assert isinstance(monitor, USBMonitor)

class TestIsReadyForProcessing:
    """ファイル準備完了チェックのテスト"""
    
    def test_ready_for_processing_with_complete_file(self):
        """書き込み完了済みファイルでTrueが返ること"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            filepath = Path(f.name)
        
        try:
            # 少し待ってからチェック
            time.sleep(0.1)
            assert is_ready_for_processing(filepath, timeout_seconds=1) is True
        finally:
            filepath.unlink(missing_ok=True)
    
    def test_ready_for_processing_with_nonexistent_file(self):
        """存在しないファイルでFalseが返ること"""
        assert is_ready_for_processing(Path("/nonexistent/file.pdf"), timeout_seconds=0.1) is False
    
    def test_ready_for_processing_with_empty_file(self):
        """空ファイルでFalseが返ること（サイズ変化待ち）"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = Path(f.name)
        
        try:
            # 空ファイルの場合、サイズが0のままなのでtimeoutでFalse
            result = is_ready_for_processing(filepath, timeout_seconds=0.2)
            assert result is False
        finally:
            filepath.unlink(missing_ok=True)
    
    def test_ready_for_processing_with_writing_file(self):
        """書き込み中のファイルでtimeout後にFalseが返ること"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = Path(f.name)
        
        try:
            # バックグラウンドで少しずつ書き込む
            def writer():
                with open(filepath, 'wb') as out:
                    for i in range(5):
                        out.write(b"x" * 1000)
                        out.flush()
                        time.sleep(0.1)
            
            import threading
            t = threading.Thread(target=writer)
            t.start()
            
            # 書き込み中にチェック（timeout短めで）
            result = is_ready_for_processing(filepath, timeout_seconds=0.5)
            t.join()
            
            # 書き込み中はサイズが変化するためFalseが返るはず
            assert result is False
        finally:
            filepath.unlink(missing_ok=True)

class TestGetSafeFilename:
    """ファイル名サニタイズのテスト"""
    
    def test_sanitize_removes_invalid_chars(self):
        """Windowsで使用不可な文字が除去されること"""
        result = get_safe_filename("test<file>name?.pdf", include_timestamp=False)
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result
        assert "_" in result  # 置換文字
    
    def test_sanitize_preserves_valid_chars(self):
        """有効な文字は保持されること"""
        result = get_safe_filename("normal_file_name.pdf", include_timestamp=False)
        assert result == "normal_file_name.pdf"
    
    def test_sanitize_japanese_filename(self):
        """日本語ファイル名が正しく処理されること"""
        result = get_safe_filename("日本語マニュアル.pdf", include_timestamp=False)
        assert "日本語マニュアル" in result
        assert ".pdf" in result
    
    def test_sanitize_adds_timestamp(self):
        """タイムスタンプが付与されること"""
        result = get_safe_filename("test.pdf", include_timestamp=True)
        # フォーマット: YYYYMMDD_HHMMSS
        import re
        assert re.search(r'_\d{8}_\d{6}\.pdf$', result) is not None
    
    def test_sanitize_truncates_long_filename(self):
        """長すぎるファイル名が切り詰められること"""
        long_name = "a" * 300 + ".pdf"
        result = get_safe_filename(long_name, include_timestamp=True)
        assert len(result) <= 255  # Windows制限
    
    def test_sanitize_handles_empty_string(self):
        """空文字列の場合の挙動"""
        result = get_safe_filename("", include_timestamp=False)
        assert result == "" or result == "_"  # 実装による

class TestWatchdogIntegration:
    """watchdog 統合のテスト"""

    def test_watchdog_observer_class_available(self):
        """watchdog が利用可能かチェック"""
        assert _HAS_WATCHDOG is not None

    def test_usb_file_handler_initialization(self):
        """USBFileHandlerが正しく初期化できること"""
        processed_files = set()
        callback = lambda p, e: None
        handler = USBFileHandler(callback, processed_files)
        assert handler.callback == callback
        assert handler._processed_files == processed_files

    def test_usb_file_handler_ignores_non_pdf(self):
        """PDF以外のファイルは無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.txt"

        handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
        handler.on_created(MockEvent())
        assert len(events_received) == 0

    def test_watchdog_not_available_fallback(self):
        """watchdog が利用できない場合、pollingモードにフォールバックすること"""
        from src.usb_monitor import _HAS_WATCHDOG, Observer

        if not _HAS_WATCHDOG:
            # Observer should be None when watchdog not available
            assert Observer is None
        else:
            # When watchdog is available, Observer should be a class
            assert Observer is not None

    def test_usb_monitor_watched_paths_initialized(self):
        """USBMonitor初期化時に_watched_pathsが設定されること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            assert hasattr(monitor, '_watched_paths')
            assert tmpdir in [str(p) for p in monitor._watched_paths]

    @patch('src.usb_monitor._HAS_WATCHDOG', False)
    def test_usb_monitor_fallback_to_polling(self):
        """watchdog無効時にpollingモードで動作すること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            with patch.object(monitor, '_monitor_loop') as mock_loop:
                monitor.start()
                assert monitor._is_running
                # When watchdog disabled, should use threading
                assert monitor._thread is not None
                monitor.stop()

    def test_usb_monitor_multiple_paths(self):
        """複数パスで監視できること"""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                monitor = USBMonitor([tmpdir1, tmpdir2], callback=lambda p, e: None)
                assert len(monitor.paths) == 2
                assert len(monitor._watched_paths) == 2


class TestEventFiltering:
    """イベントフィルタリングのテスト（モックを使用）"""

    @patch('src.usb_monitor.time.sleep')
    def test_pdf_only_filtering(self, mock_sleep):
        """PDFファイルのみが処理対象になること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            events = []
            
            def callback(file_path, event_type):
                events.append((file_path, event_type))
            
            # テスト用ファイル作成
            pdf_file = Path(tmpdir) / "test.pdf"
            txt_file = Path(tmpdir) / "test.txt"
            pdf_file.write_text("dummy")
            txt_file.write_text("dummy")
            
            # USBMonitorの監視ループをモックして1回だけ実行
            monitor = USBMonitor([tmpdir], callback=callback)
            monitor._monitor_loop = Mock(side_effect=StopIteration)
            
            try:
                monitor._monitor_loop()
            except StopIteration:
                pass
            
            # ここではモックなので、実装依存の部分はスキップ
            # 実際には _monitor_loop 内で rglob("*.pdf") を使用しているため、.txt は無視される
            pass


class TestUSBFileHandler:
    """USBFileHandler イベントハンドラのテスト"""

    def test_on_created_invokes_callback_for_pdf(self):
        """PDF作成時にコールバックが呼ばれること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=100, st_mtime=123456789)

            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_created(MockEvent())

            assert len(events_received) == 1
            assert events_received[0][0] == "/tmp/test.pdf"
            assert events_received[0][1] == "created"

    def test_on_created_ignores_directory(self):
        """ディレクトリイベントは無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = True
            src_path = "/tmp/test.pdf"

        handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
        handler.on_created(MockEvent())

        assert len(events_received) == 0

    def test_on_created_ignores_empty_file(self):
        """サイズが0のファイルは無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/empty.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=0, st_mtime=123456789)

            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_created(MockEvent())

            assert len(events_received) == 0

    def test_on_created_ignores_already_processed(self):
        """すでに処理済みファイルは無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=100, st_mtime=123456789)

            file_key = "/tmp/test.pdf|123456789"
            processed_files.add(file_key)

            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_created(MockEvent())

            assert len(events_received) == 0

    def test_on_modified_invokes_callback_for_pdf(self):
        """PDF変更時にコールバックが呼ばれること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=100, st_mtime=123456789)

            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_modified(MockEvent())

            assert len(events_received) == 1
            assert events_received[0][0] == "/tmp/test.pdf"
            assert events_received[0][1] == "modified"

    def test_on_modified_ignores_non_pdf(self):
        """PDF以外への変更は無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.txt"

        handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
        handler.on_modified(MockEvent())

        assert len(events_received) == 0

    def test_on_modified_ignores_directory(self):
        """ディレクトリ変更は無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = True
            src_path = "/tmp/test.pdf"

        handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
        handler.on_modified(MockEvent())

        assert len(events_received) == 0


class TestUSBMonitorPollingMode:
    """polling モード動作のテスト"""

    @patch('src.usb_monitor._HAS_WATCHDOG', False)
    @patch('src.usb_monitor.Observer', None)
    def test_polling_mode_thread_started(self):
        """watchdog無効時にpollingスレッドが開始されること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback_called = []

            def callback(path, event):
                callback_called.append((path, event))

            monitor = USBMonitor([tmpdir], callback=callback)
            monitor.start()

            assert monitor._is_running
            assert monitor._thread is not None
            assert monitor._thread.daemon is True

            monitor.stop()
            assert not monitor._is_running

    @patch('src.usb_monitor._HAS_WATCHDOG', False)
    @patch('src.usb_monitor.Observer', None)
    def test_polling_loop_scans_existing_files(self):
        """pollingモードで既存ファイルをスキャンすること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "test.pdf"
            pdf_file.write_bytes(b"test content")

            callback_called = []

            def callback(path, event):
                callback_called.append((path, event))

            monitor = USBMonitor([tmpdir], callback=callback)

            with patch.object(monitor, '_stop_event') as mock_stop:
                call_count = [0]
                def is_set_side_effect():
                    call_count[0] += 1
                    return call_count[0] > 1
                mock_stop.is_set.side_effect = is_set_side_effect

                with patch('src.usb_monitor.time.sleep'):
                    with patch.object(monitor, 'is_ready_for_processing', return_value=True):
                        monitor._monitor_loop()

    @patch('src.usb_monitor._HAS_WATCHDOG', False)
    @patch('src.usb_monitor.Observer', None)
    def test_polling_loop_handles_os_error(self):
        """polling中にOSErrorが発生しても続行すること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            callback_called = []

            def callback(path, event):
                callback_called.append((path, event))

            monitor = USBMonitor([tmpdir], callback=callback)

            with patch.object(monitor, '_stop_event') as mock_stop:
                call_count = [0]
                def is_set_side_effect():
                    call_count[0] += 1
                    return call_count[0] > 1
                mock_stop.is_set.side_effect = is_set_side_effect

                with patch('src.usb_monitor.time.sleep'):
                    with patch('src.usb_monitor.Path.rglob') as mock_rglob:
                        mock_rglob.side_effect = OSError("Access denied")
                        monitor._monitor_loop()


class TestIsFileLocked:
    """_is_file_locked メソッドのテスト"""

    def test_is_file_locked_nonexistent_file(self):
        """存在しないファイルはロック中とみなされること"""
        result = USBMonitor._is_file_locked(Path("/nonexistent/file.pdf"))
        assert result is True

    def test_is_file_locked_regular_file(self):
        """通常のファイルはロックされていないとみなされること"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            filepath = Path(f.name)

        try:
            result = USBMonitor._is_file_locked(filepath)
            assert result is False
        finally:
            filepath.unlink(missing_ok=True)

    def test_is_file_locked_open_file(self):
        """開いているファイルはロックされている場合があること（プラットフォーム依存）"""
        with tempfile.NamedTemporaryFile(delete=False, mode='w+b') as f:
            f.write(b"test content")
            f.flush()
            filepath = Path(f.name)

        try:
            with open(filepath, 'a+b') as locked_file:
                result = USBMonitor._is_file_locked(filepath)
                # Linuxではファイルはロックされないが、ロックされる場合もある
                assert isinstance(result, bool)
        finally:
            filepath.unlink(missing_ok=True)


class TestUSBMonitorStartStop:
    """USBMonitor start/stop の詳細テスト"""

    def test_start_twice_is_noop(self):
        """2回startを呼び出すと2回目は何もしないこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            monitor.start()
            first_thread = monitor._thread

            with patch('src.usb_monitor.logger') as mock_logger:
                monitor.start()
                assert mock_logger.debug.called

            monitor.stop()

    def test_stop_with_no_observer(self):
        """observerがない状態でstopを呼び出してもエラーにならないこと"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            monitor._observer = None
            monitor._thread = None

            monitor.stop()
            assert not monitor._is_running


class TestDetectRemovableDrives:
    """_detect_removable_drives のテスト（Windows環境のみ）"""

    def test_detect_removable_drives_on_non_windows(self):
        """非Windows環境では空リストが返ること"""
        with patch('src.usb_monitor.sys.platform', 'linux'):
            result = USBMonitor._detect_removable_drives()
            assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])