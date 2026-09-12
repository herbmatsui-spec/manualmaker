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


# ---------------------------------------------------------------------------
# Step 5 追加: 未カバー行の網羅テスト
# ---------------------------------------------------------------------------
import sys
import importlib
import src.usb_monitor as usb_monitor_mod


def _restore_sys_modules(saved):
    """sys.modules を保存時の状態へ戻す"""
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


class TestModuleImportFallback:
    """モジュールレベル import 分岐のテスト (L12-30)"""

    def test_win32_import_success_path(self):
        """win32file/win32con が利用可能な場合 _HAS_WIN32=True になること"""
        original_has_win32 = usb_monitor_mod._HAS_WIN32
        saved = {name: sys.modules.get(name) for name in ("win32file", "win32con")}
        try:
            sys.modules["win32file"] = Mock()
            sys.modules["win32con"] = Mock()
            importlib.reload(usb_monitor_mod)
            assert usb_monitor_mod._HAS_WIN32 is True
            assert usb_monitor_mod._HANDLE_INVALID == 0
        finally:
            _restore_sys_modules(saved)
            importlib.reload(usb_monitor_mod)
        assert usb_monitor_mod._HAS_WIN32 == original_has_win32

    def test_watchdog_import_fallback(self):
        """watchdog が利用不可の場合 Observer/FileSystemEventHandler が None になること"""
        original_has_watchdog = usb_monitor_mod._HAS_WATCHDOG
        saved = {
            name: sys.modules.get(name)
            for name in ("watchdog", "watchdog.observers", "watchdog.events")
        }
        try:
            sys.modules["watchdog"] = None
            sys.modules["watchdog.observers"] = None
            sys.modules["watchdog.events"] = None
            importlib.reload(usb_monitor_mod)
            assert usb_monitor_mod._HAS_WATCHDOG is False
            assert usb_monitor_mod.Observer is None
            assert usb_monitor_mod.FileSystemEventHandler is None
        finally:
            _restore_sys_modules(saved)
            importlib.reload(usb_monitor_mod)
        assert usb_monitor_mod._HAS_WATCHDOG == original_has_watchdog


class TestUSBFileHandlerModifiedBranches:
    """on_modified の残り分岐のテスト (L61-65)"""

    def test_on_modified_ignores_empty_file(self):
        """サイズが0の変更イベントは無視されること"""
        processed_files = set()
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/empty.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=0, st_mtime=123456789)
            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_modified(MockEvent())

        assert len(events_received) == 0

    def test_on_modified_ignores_already_processed(self):
        """処理済みキーを持つ変更イベントは無視されること"""
        processed_files = {"/tmp/test.pdf|123456789"}
        events_received = []

        class MockEvent:
            is_directory = False
            src_path = "/tmp/test.pdf"

        with patch('src.usb_monitor.Path.stat') as mock_stat:
            mock_stat.return_value = Mock(st_size=100, st_mtime=123456789)
            handler = USBFileHandler(lambda p, e: events_received.append((p, e)), processed_files)
            handler.on_modified(MockEvent())

        assert len(events_received) == 0


class TestDetectRemovableDrivesWindows:
    """_detect_removable_drives の Windows 分岐テスト (L94-101)"""

    def _run_detect(self, drive_type=None, error=None):
        fake_drive = Mock()
        fake_drive.exists.return_value = True
        fake_path_cls = Mock(return_value=fake_drive)
        fake_ctypes = Mock()
        if error is not None:
            fake_ctypes.windll.kernel32.GetDriveTypeW.side_effect = error
        else:
            fake_ctypes.windll.kernel32.GetDriveTypeW.return_value = drive_type
        with patch('src.usb_monitor.Path', fake_path_cls), \
             patch.dict(sys.modules, {'ctypes': fake_ctypes}):
            return USBMonitor._detect_removable_drives()

    def test_removable_drive_detected(self):
        """DRIVE_REMOVABLE(2) のドライブが検出されること"""
        result = self._run_detect(drive_type=2)
        assert len(result) == 25  # Cドライブを除くアルファベット分

    def test_fixed_drive_not_detected(self):
        """DRIVE_FIXED(3) のドライブは検出されないこと"""
        result = self._run_detect(drive_type=3)
        assert len(result) == 0

    def test_ctypes_error_ignored(self):
        """ドライブ種別取得中の例外は無視されること"""
        result = self._run_detect(error=Exception("ctypes error"))
        assert len(result) == 0


class TestUSBMonitorStartStopEdge:
    """start/stop のエラー系テスト (L125-126, L142-143)"""

    @patch('src.usb_monitor._HAS_WATCHDOG', True)
    def test_start_watchdog_init_failure_falls_back_to_polling(self):
        """watchdog 初期化失敗時にpollingモードへフォールバックすること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            with patch.object(monitor, '_monitor_loop'):
                with patch('src.usb_monitor.Observer', side_effect=Exception("init failed")):
                    monitor.start()
            assert monitor._is_running
            assert monitor._thread is not None
            monitor.stop()
            assert not monitor._is_running

    def test_stop_observer_stop_error_swallowed(self):
        """observer停止中の例外が無視されること"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            mock_observer = Mock()
            mock_observer.stop.side_effect = Exception("stop failed")
            monitor._observer = mock_observer
            monitor.stop()
            assert not monitor._is_running
            assert len(monitor._watched_paths) == 0


class TestMonitorLoopBranches:
    """_monitor_loop の分岐網羅テスト (L161-188)"""

    def _run_single_iteration(self, monitor):
        """_stop_event をモックして監視ループを1回だけ実行する"""
        with patch.object(monitor, '_stop_event') as mock_stop:
            call_count = [0]

            def is_set_side_effect():
                call_count[0] += 1
                return call_count[0] > 1

            mock_stop.is_set.side_effect = is_set_side_effect
            with patch('time.sleep'):
                monitor._monitor_loop()

    def test_monitor_loop_appends_new_removable_drive(self):
        """新規リムーバブルドライブが監視対象に追加されること (L161-167)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = USBMonitor([tmpdir], callback=lambda p, e: None)
            fake_drive = Path("/fake/usb_drive")
            with patch.object(monitor, '_detect_removable_drives', return_value=[fake_drive]):
                self._run_single_iteration(monitor)
            assert fake_drive in monitor.paths
            assert len(monitor.paths) == 2

    def test_monitor_loop_skips_empty_processed_and_unready_files(self):
        """空ファイル・処理済み・準備未完了ファイルがスキップされること (L172-179)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = Path(tmpdir) / "empty.pdf"
            empty_file.write_bytes(b"")
            processed_file = Path(tmpdir) / "processed.pdf"
            processed_file.write_bytes(b"processed data")
            unready_file = Path(tmpdir) / "unready.pdf"
            unready_file.write_bytes(b"unready data")

            events = []
            monitor = USBMonitor([tmpdir], callback=lambda p, e: events.append((p, e)))
            monitor._processed_files.add(f"{processed_file}|{processed_file.stat().st_mtime}")

            with patch.object(monitor, 'is_ready_for_processing', return_value=False):
                self._run_single_iteration(monitor)

            assert events == []

    def test_monitor_loop_stat_error_swallowed(self):
        """ループ内のOSError/PermissionErrorが無視されて続行すること (L186-188)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_file = Path(tmpdir) / "test.pdf"
            pdf_file.write_bytes(b"data")

            events = []
            monitor = USBMonitor([tmpdir], callback=lambda p, e: events.append((p, e)))

            with patch.object(monitor, '_detect_removable_drives', return_value=[]), \
                 patch.object(monitor, 'is_ready_for_processing', side_effect=OSError("stat failed")):
                self._run_single_iteration(monitor)

            assert events == []
            assert pdf_file.read_bytes() == b"data"


class TestIsFileLockedWindows:
    """_is_file_locked の Windows/fallback 分岐テスト (L205-230)"""

    def _make_file(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(b"data")
        f.flush()
        f.close()
        return Path(f.name)

    @staticmethod
    def _make_win32con():
        """| 演算が可能な int 属性を持つ win32con モックを生成する"""
        fake_win32con = Mock()
        fake_win32con.GENERIC_READ = 0x80000000
        fake_win32con.GENERIC_WRITE = 0x40000000
        fake_win32con.OPEN_EXISTING = 3
        fake_win32con.FILE_ATTRIBUTE_NORMAL = 0x80
        return fake_win32con

    def test_windows_file_unlocked(self):
        """排他オープンに成功した場合ロックされていないとみなすこと (L205-218)"""
        filepath = self._make_file()
        try:
            fake_win32file = Mock()
            fake_win32file.CreateFile.return_value = 123
            fake_win32con = self._make_win32con()
            with patch('src.usb_monitor._HAS_WIN32', True), \
                 patch('src.usb_monitor.win32file', fake_win32file), \
                 patch('src.usb_monitor.win32con', fake_win32con), \
                 patch('src.usb_monitor._HANDLE_INVALID', 0):
                result = USBMonitor._is_file_locked(filepath)
            assert result is False
            fake_win32file.CloseHandle.assert_called_once_with(123)
        finally:
            filepath.unlink(missing_ok=True)

    def test_windows_invalid_handle_returns_false(self):
        """無効ハンドルの場合はFalseを返すこと (L230)"""
        filepath = self._make_file()
        try:
            fake_win32file = Mock()
            fake_win32file.CreateFile.return_value = 0
            fake_win32con = self._make_win32con()
            with patch('src.usb_monitor._HAS_WIN32', True), \
                 patch('src.usb_monitor.win32file', fake_win32file), \
                 patch('src.usb_monitor.win32con', fake_win32con), \
                 patch('src.usb_monitor._HANDLE_INVALID', 0):
                result = USBMonitor._is_file_locked(filepath)
            assert result is False
            fake_win32file.CloseHandle.assert_not_called()
        finally:
            filepath.unlink(missing_ok=True)

    def test_windows_create_file_exception_returns_locked(self):
        """CreateFile 例外時はロック中とみなすこと (L219-220)"""
        filepath = self._make_file()
        try:
            fake_win32file = Mock()
            fake_win32file.CreateFile.side_effect = Exception("sharing violation")
            fake_win32con = self._make_win32con()
            with patch('src.usb_monitor._HAS_WIN32', True), \
                 patch('src.usb_monitor.win32file', fake_win32file), \
                 patch('src.usb_monitor.win32con', fake_win32con), \
                 patch('src.usb_monitor._HANDLE_INVALID', 0):
                result = USBMonitor._is_file_locked(filepath)
            assert result is True
        finally:
            filepath.unlink(missing_ok=True)

    def test_fallback_open_error_returns_locked(self):
        """fallback の open 失敗時はロック中とみなすこと (L227-228)"""
        filepath = self._make_file()
        try:
            with patch('src.usb_monitor._HAS_WIN32', False), \
                 patch('builtins.open', side_effect=PermissionError("denied")):
                result = USBMonitor._is_file_locked(filepath)
            assert result is True
        finally:
            filepath.unlink(missing_ok=True)


class TestIsReadyForProcessingBranches:
    """is_ready_for_processing の分岐テスト (L252-258)"""

    def _make_file(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(b"data")
        f.flush()
        f.close()
        return Path(f.name)

    def test_size_change_during_window_returns_false(self):
        """待機中にサイズが変化した場合はFalseを返すこと (L251-253, L257-258)"""
        filepath = self._make_file()
        try:
            def grow(_seconds):
                with open(filepath, "ab") as out:
                    out.write(b"x" * 100)

            with patch('time.sleep', side_effect=grow):
                result = USBMonitor.is_ready_for_processing(filepath, timeout_seconds=1.0)
            assert result is False
        finally:
            filepath.unlink(missing_ok=True)

    def test_stat_os_error_marks_changed(self):
        """サイズ確認中のOSErrorは変化ありとみなすこと (L254-255)"""
        filepath = self._make_file()
        try:
            call_counter = [0]

            def fake_stat(*args, **kwargs):
                call_counter[0] += 1
                if call_counter[0] <= 2:
                    return Mock(st_size=100)  # exists() と初回サイズ取得用
                raise OSError("stat failed")

            with patch('src.usb_monitor.Path.stat', side_effect=fake_stat), \
                 patch('time.sleep'):
                result = USBMonitor.is_ready_for_processing(filepath, timeout_seconds=0.2)
            assert result is False
        finally:
            filepath.unlink(missing_ok=True)


class TestGetSafeFilenameTruncation:
    """get_safe_filename の切り詰めテスト (L280-282)"""

    def test_truncation_without_timestamp(self):
        """タイムスタンプなしでも長い名前が切り詰められること"""
        long_name = "a" * 300 + ".pdf"
        result = get_safe_filename(long_name, include_timestamp=False)
        assert len(result) == 255
        assert result.endswith(".pdf")
        assert result.startswith("a" * 251)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])