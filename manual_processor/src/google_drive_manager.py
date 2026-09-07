"""
Google Drive Manager Module
Handles OAuth2 authentication and file upload for Google Drive integration.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.security.keyring_store import get_api_key, set_api_key, delete_api_key, key_exists

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

KEYRING_SERVICE = "manual_processor"
KEYRING_REFRESH_TOKEN_USERNAME = "google_drive_refresh_token"
KEYRING_CREDENTIALS_USERNAME = "google_drive_credentials"

try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GoogleDriveError(Exception):
    """Google Drive operation error"""
    pass


@dataclass
class DriveFile:
    """Represents a file uploaded to Google Drive"""
    file_id: str
    name: str
    web_view_link: str
    web_content_link: str
    mime_type: str


class GoogleDriveManager:
    """Manages Google Drive authentication and file operations"""

    def __init__(self, credentials_path: Path):
        """
        Initialize Google Drive manager

        Args:
            credentials_path: Path to OAuth2 client secrets JSON
        """
        self.credentials_path = Path(credentials_path)
        self._creds = None

    def is_authenticated(self) -> bool:
        """Check if user has stored refresh token"""
        return key_exists(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN_USERNAME)

    def get_authorization_url(self, redirect_uri: Optional[str] = None) -> str:
        """
        Generate OAuth2 authorization URL

        Args:
            redirect_uri: OAuth2 redirect URI

        Returns:
            Authorization URL string
        """
        if not self.credentials_path.exists():
            raise GoogleDriveError(f"Credentials file not found: {self.credentials_path}")

        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_secrets_file(
                str(self.credentials_path),
                scopes=SCOPES,
            )
            if redirect_uri:
                flow.redirect_uri = redirect_uri

            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
                include_granted_scopes="true",
            )
            return auth_url
        except Exception as e:
            raise GoogleDriveError(f"Failed to generate authorization URL: {e}") from e

    def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens

        Args:
            code: Authorization code from OAuth2 callback
            redirect_uri: OAuth2 redirect URI

        Returns:
            Token info dict with access_token, refresh_token, expires_in, etc.
        """
        if not self.credentials_path.exists():
            raise GoogleDriveError(f"Credentials file not found: {self.credentials_path}")

        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_secrets_file(
                str(self.credentials_path),
                scopes=SCOPES,
            )
            if redirect_uri:
                flow.redirect_uri = redirect_uri

            flow.fetch_token(code=code)
            creds = flow.credentials

            if not creds.refresh_token:
                raise GoogleDriveError("No refresh token received. Please ensure access_type=offline.")

            token_info = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or SCOPES),
            }

            set_api_key(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN_USERNAME, creds.refresh_token)
            set_api_key(KEYRING_SERVICE, KEYRING_CREDENTIALS_USERNAME, json.dumps(token_info))

            self._creds = creds
            return token_info

        except GoogleDriveError:
            raise
        except Exception as e:
            raise GoogleDriveError(f"Failed to exchange authorization code: {e}") from e

    def _load_credentials(self):
        """Load and refresh credentials from keyring"""
        refresh_token = get_api_key(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN_USERNAME)
        if not refresh_token:
            raise GoogleDriveError("Not authenticated. No refresh token found.")

        creds_json = get_api_key(KEYRING_SERVICE, KEYRING_CREDENTIALS_USERNAME)
        if creds_json:
            try:
                token_info = json.loads(creds_json)
                from google.oauth2.credentials import Credentials
                creds = Credentials(
                    token=token_info.get("token"),
                    refresh_token=token_info.get("refresh_token"),
                    token_uri=token_info.get("token_uri", "https://oauth2.googleapis.com/token"),
                    client_id=token_info.get("client_id"),
                    client_secret=token_info.get("client_secret"),
                    scopes=token_info.get("scopes", SCOPES),
                )
            except Exception as e:
                raise GoogleDriveError(f"Failed to parse stored credentials: {e}") from e
        else:
            from google.oauth2.credentials import Credentials
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=None,
                client_secret=None,
                scopes=SCOPES,
            )

        if creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                token_info = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes or SCOPES),
                }
                set_api_key(KEYRING_SERVICE, KEYRING_CREDENTIALS_USERNAME, json.dumps(token_info))
            except Exception as e:
                raise GoogleDriveError(f"Failed to refresh access token: {e}") from e

        self._creds = creds
        return creds

    def _get_drive_service(self):
        """Get authenticated Google Drive service"""
        creds = self._load_credentials()
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=creds)

    def upload_file(self, file_path: Path, folder_id: Optional[str] = None,
                    mime_type: str = "application/pdf") -> DriveFile:
        """
        Upload file to Google Drive and return file info

        Args:
            file_path: Local file path to upload
            folder_id: Optional Google Drive folder ID
            mime_type: MIME type of the file

        Returns:
            DriveFile with file_id and web links
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise GoogleDriveError(f"File not found: {file_path}")

        try:
            service = self._get_drive_service()

            file_metadata = {"name": file_path.name}
            if folder_id:
                file_metadata["parents"] = [folder_id]

            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(
                str(file_path),
                mimetype=mime_type,
                resumable=True,
            )

            uploaded = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, mimeType, webViewLink, webContentLink",
            ).execute()

            drive_file = DriveFile(
                file_id=uploaded.get("id", ""),
                name=uploaded.get("name", file_path.name),
                web_view_link=uploaded.get("webViewLink", ""),
                web_content_link=uploaded.get("webContentLink", ""),
                mime_type=uploaded.get("mimeType", mime_type),
            )

            logger.info(f"Uploaded to Google Drive: {drive_file.file_id}")
            return drive_file

        except GoogleDriveError:
            raise
        except Exception as e:
            raise GoogleDriveError(f"Failed to upload file to Google Drive: {e}") from e

    def set_public_read(self, file_id: str) -> None:
        """
        Set file permission to 'anyone with link can read'

        Args:
            file_id: Google Drive file ID
        """
        try:
            service = self._get_drive_service()
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
            logger.info(f"Set public read permission for file: {file_id}")
        except GoogleDriveError:
            raise
        except Exception as e:
            raise GoogleDriveError(f"Failed to set public read permission: {e}") from e

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """
        Create a folder in Google Drive

        Args:
            folder_name: Name of the folder
            parent_id: Optional parent folder ID

        Returns:
            Created folder ID
        """
        try:
            service = self._get_drive_service()
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                file_metadata["parents"] = [parent_id]

            folder = service.files().create(
                body=file_metadata,
                fields="id",
            ).execute()
            folder_id = folder.get("id", "")
            logger.info(f"Created Google Drive folder: {folder_name} ({folder_id})")
            return folder_id
        except GoogleDriveError:
            raise
        except Exception as e:
            raise GoogleDriveError(f"Failed to create folder: {e}") from e

    def revoke_authentication(self) -> None:
        """Remove stored refresh token and credentials"""
        try:
            delete_api_key(KEYRING_SERVICE, KEYRING_REFRESH_TOKEN_USERNAME)
            delete_api_key(KEYRING_SERVICE, KEYRING_CREDENTIALS_USERNAME)
            self._creds = None
            logger.info("Revoked Google Drive authentication")
        except Exception as e:
            logger.warning(f"Failed to fully revoke authentication: {e}")
