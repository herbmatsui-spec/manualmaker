"""
Tests for Google Drive Manager module
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.google_drive_manager import GoogleDriveManager, GoogleDriveError, DriveFile, GOOGLE_API_AVAILABLE


def keyring_is_available() -> bool:
    """Check if keyring backend is available"""
    try:
        import keyring
        keyring.get_password("test", "test")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API libraries not installed")
@pytest.mark.skipif(not keyring_is_available(), reason="No keyring backend available")
class TestGoogleDriveManagerInit:
    """Test GoogleDriveManager initialization"""

    def test_init_with_credentials_path(self):
        """Test initialization with credentials path"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test"}}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)
            assert manager.credentials_path == creds_path
            assert manager._creds is None
        finally:
            creds_path.unlink()

    def test_init_creds_path_as_string(self):
        """Test initialization with string path"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test"}}')
            creds_path_str = f.name

        try:
            manager = GoogleDriveManager(credentials_path=creds_path_str)
            assert manager.credentials_path == Path(creds_path_str)
        finally:
            Path(creds_path_str).unlink()


@pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API libraries not installed")
@pytest.mark.skipif(not keyring_is_available(), reason="No keyring backend available")
@pytest.mark.skipif(not GOOGLE_API_AVAILABLE, reason="Google API libraries not installed")
@pytest.mark.skipif(not keyring_is_available(), reason="No keyring backend available")
class TestGoogleDriveManagerAuth:
    """Test authentication methods"""

    @patch('src.google_drive_manager.key_exists')
    def test_is_authenticated_true(self, mock_key_exists):
        """Test is_authenticated returns True when token exists"""
        mock_key_exists.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)
            assert manager.is_authenticated() is True
            mock_key_exists.assert_called_once()
        finally:
            creds_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    def test_is_authenticated_false(self, mock_key_exists):
        """Test is_authenticated returns False when no token"""
        mock_key_exists.return_value = False

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)
            assert manager.is_authenticated() is False
        finally:
            creds_path.unlink()

    def test_get_authorization_url_requires_credentials(self):
        """Test get_authorization_url raises when no credentials file"""
        manager = GoogleDriveManager(credentials_path=Path("/nonexistent/credentials.json"))
        with pytest.raises(GoogleDriveError, match="Credentials file not found"):
            manager.get_authorization_url()

    def test_get_authorization_url_returns_url(self):
        """Test get_authorization_url returns a URL string"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test-client-id", "client_secret": "test-secret"}}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)

            mock_flow = Mock()
            mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/v2/auth?test", "state")

            with patch('google_auth_oauthlib.flow.Flow') as mock_flow_cls:
                mock_flow_cls.from_client_secrets_file.return_value = mock_flow
                url = manager.get_authorization_url(redirect_uri="http://localhost:8080")
                assert url.startswith("https://accounts.google.com")
        finally:
            creds_path.unlink()

    @patch('src.google_drive_manager.set_api_key')
    def test_exchange_code_stores_tokens(self, mock_set_api_key):
        """Test exchange_code stores refresh token"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test", "client_secret": "test"}}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)

            mock_flow = Mock()
            mock_creds = Mock()
            mock_creds.refresh_token = "test_refresh_token"
            mock_creds.token = "test_access_token"
            mock_creds.token_uri = "https://oauth2.googleapis.com/token"
            mock_creds.client_id = "test_client_id"
            mock_creds.client_secret = "test_client_secret"
            mock_creds.scopes = ["https://www.googleapis.com/auth/drive.file"]
            mock_flow.credentials = mock_creds
            mock_flow.fetch_token.return_value = None

            with patch('google_auth_oauthlib.flow.Flow.from_client_secrets_file', return_value=mock_flow):
                result = manager.exchange_code("auth_code_123", redirect_uri="http://localhost:8080")

            assert result["refresh_token"] == "test_refresh_token"
            assert result["token"] == "test_access_token"
            assert mock_set_api_key.call_count == 2
        finally:
            creds_path.unlink()

    @patch('src.google_drive_manager.set_api_key')
    def test_exchange_code_missing_refresh_token_raises(self, mock_set_api_key):
        """Test exchange_code raises when no refresh token received"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test"}}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)

            mock_flow = Mock()
            mock_creds = Mock()
            mock_creds.refresh_token = None
            mock_flow.credentials = mock_creds
            mock_flow.fetch_token.return_value = None

            with patch('google_auth_oauthlib.flow.Flow.from_client_secrets_file', return_value=mock_flow):
                with pytest.raises(GoogleDriveError, match="No refresh token"):
                    manager.exchange_code("auth_code_123")
        finally:
            creds_path.unlink()

    def test_revoke_authentication(self):
        """Test revoking authentication removes stored tokens"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{}')
            creds_path = Path(f.name)

        try:
            manager = GoogleDriveManager(credentials_path=creds_path)

            with patch('src.google_drive_manager.delete_api_key') as mock_delete:
                manager.revoke_authentication()

            assert mock_delete.call_count == 2
            assert manager._creds is None
        finally:
            creds_path.unlink()


class TestGoogleDriveManagerUpload:
    """Test file upload operations"""

    def _create_manager_with_creds(self):
        """Helper to create manager with mocked credentials"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"installed": {"client_id": "test"}}')
            creds_path = Path(f.name)

        manager = GoogleDriveManager(credentials_path=creds_path)

        mock_creds = Mock()
        mock_creds.expired = False
        mock_creds.refresh_token = "test_refresh"
        mock_creds.token = "test_token"
        manager._creds = mock_creds

        return manager, creds_path

    @patch('src.google_drive_manager.key_exists')
    @patch('src.google_drive_manager.get_api_key')
    def test_upload_file_success(self, mock_get_api_key, mock_key_exists):
        """Test successful file upload"""
        mock_key_exists.return_value = True
        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "test_refresh_token"
            return None
        mock_get_api_key.side_effect = get_api_key_side_effect

        manager, creds_path = self._create_manager_with_creds()

        mock_service = Mock()
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {
            "id": "drive_file_123",
            "name": "test.pdf",
            "mimeType": "application/pdf",
            "webViewLink": "https://drive.google.com/file/d/drive_file_123/view",
            "webContentLink": "https://drive.google.com/uc?id=drive_file_123",
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf content")
            file_path = Path(f.name)

        try:
            with patch('googleapiclient.discovery.build', return_value=mock_service):
                result = manager.upload_file(file_path, mime_type="application/pdf")

            assert isinstance(result, DriveFile)
            assert result.file_id == "drive_file_123"
            assert result.web_view_link == "https://drive.google.com/file/d/drive_file_123/view"
        finally:
            creds_path.unlink()
            file_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    def test_upload_file_not_found(self, mock_key_exists):
        """Test upload raises when file not found"""
        mock_key_exists.return_value = True
        manager, creds_path = self._create_manager_with_creds()

        with pytest.raises(GoogleDriveError, match="File not found"):
            manager.upload_file(Path("/nonexistent/file.pdf"))

        creds_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    @patch('src.google_drive_manager.get_api_key')
    def test_upload_file_to_folder(self, mock_get_api_key, mock_key_exists):
        """Test uploading to specific folder"""
        mock_key_exists.return_value = True
        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "test_refresh_token"
            return None
        mock_get_api_key.side_effect = get_api_key_side_effect

        manager, creds_path = self._create_manager_with_creds()

        mock_service = Mock()
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {
            "id": "drive_file_456",
            "name": "manual.pdf",
            "mimeType": "application/pdf",
            "webViewLink": "https://drive.google.com/file/d/drive_file_456/view",
            "webContentLink": "https://drive.google.com/uc?id=drive_file_456",
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            file_path = Path(f.name)

        try:
            with patch('googleapiclient.discovery.build', return_value=mock_service):
                result = manager.upload_file(file_path, folder_id="folder_123", mime_type="application/pdf")

            assert result.file_id == "drive_file_456"
            call_args = mock_files.create.call_args
            assert call_args[1]["body"]["parents"] == ["folder_123"]
        finally:
            creds_path.unlink()
            file_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    @patch('src.google_drive_manager.get_api_key')
    def test_set_public_read(self, mock_get_api_key, mock_key_exists):
        """Test setting public read permission"""
        mock_key_exists.return_value = True
        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "test_refresh_token"
            elif username == "google_drive_credentials":
                return json.dumps({"token": "test_token", "refresh_token": "test_refresh", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "test", "client_secret": "test", "scopes": ["https://www.googleapis.com/auth/drive.file"]})
            return None
        mock_get_api_key.side_effect = get_api_key_side_effect

        manager, creds_path = self._create_manager_with_creds()

        mock_service = Mock()
        mock_perms = Mock()
        mock_service.permissions.return_value = mock_perms
        mock_create = Mock()
        mock_perms.create.return_value = mock_create
        mock_create.execute.return_value = {"id": "perm_123"}

        with patch('googleapiclient.discovery.build', return_value=mock_service):
            manager.set_public_read("file_123")
            mock_perms.create.assert_called_once()

        creds_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    @patch('src.google_drive_manager.get_api_key')
    def test_create_folder(self, mock_get_api_key, mock_key_exists):
        """Test folder creation"""
        mock_key_exists.return_value = True
        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "test_refresh_token"
            return None
        mock_get_api_key.side_effect = get_api_key_side_effect

        manager, creds_path = self._create_manager_with_creds()

        mock_service = Mock()
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {"id": "folder_789"}

        with patch('googleapiclient.discovery.build', return_value=mock_service):
            folder_id = manager.create_folder("Test Folder", parent_id="parent_123")
            assert folder_id == "folder_789"
            call_args = mock_files.create.call_args
            assert call_args[1]["body"]["mimeType"] == "application/vnd.google-apps.folder"

        creds_path.unlink()

    @patch('src.google_drive_manager.key_exists')
    @patch('src.google_drive_manager.get_api_key')
    def test_create_folder_no_parent(self, mock_get_api_key, mock_key_exists):
        """Test folder creation without parent"""
        mock_key_exists.return_value = True
        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "test_refresh_token"
            return None
        mock_get_api_key.side_effect = get_api_key_side_effect

        manager, creds_path = self._create_manager_with_creds()

        mock_service = Mock()
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {"id": "folder_root"}

        with patch('googleapiclient.discovery.build', return_value=mock_service):
            folder_id = manager.create_folder("Root Folder")
            assert folder_id == "folder_root"
            call_args = mock_files.create.call_args
            assert "parents" not in call_args[1]["body"]

        creds_path.unlink()


def _make_manager(tmp_path):
    """Helper: create manager with a temporary credentials file"""
    creds_file = tmp_path / "creds.json"
    creds_file.write_text('{"installed": {"client_id": "test"}}')
    return GoogleDriveManager(credentials_path=creds_file)


class TestGoogleDriveManagerErrorPaths:
    """Test exception wrapping in each method"""

    def test_get_authorization_url_wraps_error(self, tmp_path):
        manager = _make_manager(tmp_path)
        with patch('google_auth_oauthlib.flow.Flow.from_client_secrets_file',
                   side_effect=RuntimeError("bad secrets")):
            with pytest.raises(GoogleDriveError, match="Failed to generate authorization URL"):
                manager.get_authorization_url()

    def test_exchange_code_requires_credentials(self, tmp_path):
        manager = GoogleDriveManager(credentials_path=tmp_path / "missing.json")
        with pytest.raises(GoogleDriveError, match="Credentials file not found"):
            manager.exchange_code("code123")

    def test_exchange_code_wraps_error(self, tmp_path):
        manager = _make_manager(tmp_path)
        with patch('google_auth_oauthlib.flow.Flow.from_client_secrets_file',
                   side_effect=RuntimeError("flow failed")):
            with pytest.raises(GoogleDriveError, match="Failed to exchange authorization code"):
                manager.exchange_code("code123")

    def test_load_credentials_no_refresh_token_raises(self, tmp_path):
        manager = _make_manager(tmp_path)
        with patch('src.google_drive_manager.get_api_key', return_value=None):
            with pytest.raises(GoogleDriveError, match="Not authenticated"):
                manager._load_credentials()

    def test_load_credentials_invalid_json_raises(self, tmp_path):
        manager = _make_manager(tmp_path)

        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "refresh_token_value"
            return "{invalid json!!"

        with patch('src.google_drive_manager.get_api_key', side_effect=get_api_key_side_effect):
            with pytest.raises(GoogleDriveError, match="Failed to parse stored credentials"):
                manager._load_credentials()

    def test_load_credentials_without_stored_json(self, tmp_path):
        manager = _make_manager(tmp_path)

        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "refresh_token_value"
            return None

        with patch('src.google_drive_manager.get_api_key', side_effect=get_api_key_side_effect):
            creds = manager._load_credentials()
        assert creds.refresh_token == "refresh_token_value"
        assert manager._creds is creds

    def test_load_credentials_refreshes_expired_token(self, tmp_path):
        manager = _make_manager(tmp_path)

        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "refresh_token_value"
            return json.dumps({
                "token": "old_token",
                "refresh_token": "refresh_token_value",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "cid",
                "client_secret": "csecret",
                "scopes": ["https://www.googleapis.com/auth/drive.file"],
            })

        mock_creds = Mock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_value"
        mock_creds.token = "new_token"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_creds.client_id = "cid"
        mock_creds.client_secret = "csecret"
        mock_creds.scopes = ["https://www.googleapis.com/auth/drive.file"]

        with patch('src.google_drive_manager.get_api_key', side_effect=get_api_key_side_effect), \
             patch('google.oauth2.credentials.Credentials', return_value=mock_creds):
            creds = manager._load_credentials()

        mock_creds.refresh.assert_called_once()
        assert creds.token == "new_token"
        assert manager._creds is creds

    def test_load_credentials_refresh_error_raises(self, tmp_path):
        manager = _make_manager(tmp_path)

        def get_api_key_side_effect(service, username):
            if username == "google_drive_refresh_token":
                return "refresh_token_value"
            return json.dumps({"token": "t", "refresh_token": "refresh_token_value"})

        mock_creds = Mock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token_value"
        mock_creds.refresh.side_effect = RuntimeError("refresh failed")

        with patch('src.google_drive_manager.get_api_key', side_effect=get_api_key_side_effect), \
             patch('google.oauth2.credentials.Credentials', return_value=mock_creds):
            with pytest.raises(GoogleDriveError, match="Failed to refresh access token"):
                manager._load_credentials()

    def test_upload_file_wraps_error(self, tmp_path):
        manager = _make_manager(tmp_path)
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"pdf")

        with patch('src.google_drive_manager.get_api_key', return_value=None), \
             patch.object(GoogleDriveManager, '_get_drive_service',
                          side_effect=RuntimeError("service down")):
            with pytest.raises(GoogleDriveError, match="Failed to upload file to Google Drive"):
                manager.upload_file(test_file)

    def test_upload_file_reuses_google_drive_error(self, tmp_path):
        manager = _make_manager(tmp_path)
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"pdf")

        original_error = GoogleDriveError("propagated")
        with patch.object(GoogleDriveManager, '_get_drive_service', side_effect=original_error):
            with pytest.raises(GoogleDriveError) as exc_info:
                manager.upload_file(test_file)
        assert exc_info.value is original_error

    def test_set_public_read_wraps_error(self, tmp_path):
        manager = _make_manager(tmp_path)

        with patch.object(GoogleDriveManager, '_get_drive_service',
                          side_effect=RuntimeError("perm failed")):
            with pytest.raises(GoogleDriveError, match="Failed to set public read permission"):
                manager.set_public_read("file_1")

    def test_set_public_read_reuses_google_drive_error(self, tmp_path):
        manager = _make_manager(tmp_path)

        original_error = GoogleDriveError("propagated")
        with patch.object(GoogleDriveManager, '_get_drive_service', side_effect=original_error):
            with pytest.raises(GoogleDriveError) as exc_info:
                manager.set_public_read("file_1")
        assert exc_info.value is original_error

    def test_create_folder_wraps_error(self, tmp_path):
        manager = _make_manager(tmp_path)

        with patch.object(GoogleDriveManager, '_get_drive_service',
                          side_effect=RuntimeError("folder failed")):
            with pytest.raises(GoogleDriveError, match="Failed to create folder"):
                manager.create_folder("New Folder")

    def test_create_folder_reuses_google_drive_error(self, tmp_path):
        manager = _make_manager(tmp_path)

        original_error = GoogleDriveError("propagated")
        with patch.object(GoogleDriveManager, '_get_drive_service', side_effect=original_error):
            with pytest.raises(GoogleDriveError) as exc_info:
                manager.create_folder("New Folder")
        assert exc_info.value is original_error

    def test_revoke_authentication_exception_swallowed(self, tmp_path, caplog):
        import logging
        manager = _make_manager(tmp_path)

        with patch('src.google_drive_manager.delete_api_key',
                   side_effect=RuntimeError("keyring error")):
            manager.revoke_authentication()  # should not raise

        assert any("Failed to fully revoke" in r.message for r in caplog.records)


class TestGoogleDriveModuleFallback:
    """Test module-level ImportError fallback (lines 23-24, 41-42)"""

    def test_import_fallback_flags(self):
        # GOOGLE_API_AVAILABLE の現在値を検証（環境により True/False）
        import src.google_drive_manager as gdm
        assert isinstance(gdm.GOOGLE_API_AVAILABLE, bool)

    def test_fallback_when_google_libs_missing(self):
        import importlib
        import sys
        import src.google_drive_manager as gdm

        # reload によりクラスオブジェクトの同一性が変わるため元の例外クラスを保存する
        # （src.web.app など他モジュールが元のクラスを except 句で参照しているため）
        original_error_cls = gdm.GoogleDriveError

        google_mods = {name: mod for name, mod in sys.modules.items()
                       if name == "google" or name.startswith("google.")
                       or name.startswith("google_auth_oauthlib")
                       or name.startswith("googleapiclient")}
        for name in google_mods:
            del sys.modules[name]
        sys.modules["google"] = None
        sys.modules["google_auth_oauthlib"] = None
        sys.modules["googleapiclient"] = None
        try:
            importlib.reload(gdm)
            assert gdm.GOOGLE_API_AVAILABLE is False
        finally:
            for name in ("google", "google_auth_oauthlib", "googleapiclient"):
                del sys.modules[name]
            sys.modules.update(google_mods)
            importlib.reload(gdm)
            # 例外クラスの同一性を復元（テスト順序依存の失敗を防ぐ）
            gdm.GoogleDriveError = original_error_cls
