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
