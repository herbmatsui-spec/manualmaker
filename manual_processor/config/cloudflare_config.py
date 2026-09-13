"""
Cloudflare-specific configuration for Pages Functions / Workers
Provides bindings and environment-aware settings
"""

import os
from typing import Optional, Any, List
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CloudflareBindings:
    """Cloudflare Pages Functions / Workers bindings"""
    # R2 Bucket
    FILES: Any = None
    
    # Queue
    PDF_QUEUE: Any = None
    
    # Durable Object
    PROGRESS_DO: Any = None
    
    # KV
    RATE_LIMIT_KV: Any = None
    
    # Service binding to Pages Functions
    PAGES_FUNCTIONS: Any = None
    
    # D1 Database (optional)
    DB: Any = None


class CloudflareConfig:
    """Cloudflare-aware configuration"""
    
    _instance: Optional['CloudflareConfig'] = None
    _bindings: Optional[CloudflareBindings] = None
    
    def __init__(self, bindings: Optional[CloudflareBindings] = None):
        self.bindings = bindings or CloudflareBindings()
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8788")
        self.r2_bucket_name = os.getenv("R2_BUCKET_NAME", "manual-processor-files")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "")
        
        # API Keys (from secrets)
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "")
        self.jwt_secret = os.getenv("JWT_SECRET", "")
        
        # R2 Credentials (for local development)
        self.r2_endpoint_url = os.getenv("R2_ENDPOINT_URL", "")
        self.r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "")
        self.r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
        
        # Google Cloud
        self.google_cloud_project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
        self.google_application_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        
        # Processing settings
        self.max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
        self.web_upload_max_mb = int(os.getenv("WEB_UPLOAD_MAX_MB", "100"))
        self.pdf_dpi = int(os.getenv("PDF_DPI", "300"))
        self.supported_extensions = os.getenv("SUPPORTED_EXTENSIONS", ".pdf").split(",")
        self.default_language = os.getenv("DEFAULT_LANGUAGE", "ja")
        
        # Processing options
        self.processor_type = os.getenv("PROCESSOR_TYPE", "gemini")
        self.gemini_model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        self.gemini_temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
        self.gemini_max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048"))
        
        # Prompt settings
        self.prompt_layout = os.getenv("PROMPT_LAYOUT", "horizontal")
        self.prompt_strict_mode = os.getenv("PROMPT_STRICT_MODE", "true").lower() == "true"
        self.prompt_has_diagrams = os.getenv("PROMPT_HAS_DIAGRAMS", "false").lower() == "true"
        self.prompt_low_quality_mode = os.getenv("PROMPT_LOW_QUALITY_MODE", "false").lower() == "true"
        
        # Output settings
        self.generate_diagram = os.getenv("GENERATE_DIAGRAM", "true").lower() == "true"
        self.generate_diagram_png = os.getenv("GENERATE_DIAGRAM_PNG", "true").lower() == "true"
        self.generate_diagram_markdown = os.getenv("GENERATE_DIAGRAM_MARKDOWN", "true").lower() == "true"
        self.generate_diagram_mermaid = os.getenv("GENERATE_DIAGRAM_MERMAID", "false").lower() == "true"
        
        # TTS settings
        self.tts_language_code = os.getenv("TTS_LANGUAGE_CODE", "ja-JP")
        self.tts_voice_name = os.getenv("TTS_VOICE_NAME", "ja-JP-Standard-A")
        
        # Security
        self.pii_masking_enabled = os.getenv("PII_MASKING_ENABLED", "false").lower() == "true"
        
        # Google Drive
        self.drive_enabled = os.getenv("DRIVE_ENABLED", "false").lower() == "true"
        self.drive_auto_upload = os.getenv("DRIVE_AUTO_UPLOAD", "false").lower() == "true"
        self.drive_share_public = os.getenv("DRIVE_SHARE_PUBLIC", "true").lower() == "true"
        self.drive_folder_id = os.getenv("DRIVE_FOLDER_ID", "")
        self.drive_folder_name = os.getenv("DRIVE_FOLDER_NAME", "ManualMaker")
        self.drive_credentials_path = os.getenv("DRIVE_CREDENTIALS_PATH", "")
        
        # Paths (use temp directories in Cloudflare)
        self.temp_directory = Path(os.getenv("TEMP_DIRECTORY", "/tmp"))
        self.output_directory = Path(os.getenv("OUTPUT_DIRECTORY", "/tmp/output"))
        
        # Ensure directories exist
        self.temp_directory.mkdir(parents=True, exist_ok=True)
        self.output_directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_cloudflare(self) -> bool:
        """Check if running in Cloudflare environment"""
        # Only consider it Cloudflare if explicitly set to production/preview
        # Having bindings doesn't mean we're in Cloudflare (could be local testing)
        return self.environment in ("production", "preview")
    
    @property
    def is_local(self) -> bool:
        """Check if running locally"""
        return self.environment not in ("production", "preview")
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins"""
        if self.is_cloudflare:
            return [o.strip() for o in self.allowed_origins if o.strip()]
        return ["http://localhost:3000", "http://localhost:8000", "http://localhost:8788"]
    
    def get_r2_client(self):
        """Get R2 client from bindings or create local client"""
        if self.bindings.FILES:
            return self.bindings.FILES
        
        # Local development - use boto3 with MinIO/LocalStack
        try:
            import boto3
            if self.r2_endpoint_url:
                return boto3.client(
                    's3',
                    endpoint_url=self.r2_endpoint_url,
                    aws_access_key_id=self.r2_access_key_id,
                    aws_secret_access_key=self.r2_secret_access_key,
                    region_name="auto"
                )
        except ImportError:
            pass
        return None
    
    def get_queue(self):
        """Get Queue binding"""
        return self.bindings.PDF_QUEUE
    
    def get_progress_do(self):
        """Get Durable Object binding"""
        return self.bindings.PROGRESS_DO
    
    def get_kv(self):
        """Get KV binding"""
        return self.bindings.RATE_LIMIT_KV
    
    @classmethod
    def set_bindings(cls, bindings: CloudflareBindings) -> None:
        """Set Cloudflare bindings (called from Pages Functions context)"""
        if cls._instance:
            cls._instance.bindings = bindings
        cls._bindings = bindings
    
    @classmethod
    def get_instance(cls) -> 'CloudflareConfig':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls(cls._bindings)
        return cls._instance
    
    @classmethod
    def from_bindings(cls, bindings: CloudflareBindings) -> 'CloudflareConfig':
        """Create instance from bindings"""
        return cls(bindings)


# Backward compatibility with existing Config interface
class Config:
    """Backward-compatible Config interface"""
    
    _cf_config: Optional[CloudflareConfig] = None
    
    def __init__(self):
        self._cf_config = CloudflareConfig.get_instance()
    
    @classmethod
    def get_instance(cls) -> 'Config':
        if not hasattr(cls, '_singleton'):
            cls._singleton = cls()
        return cls._singleton
    
    @classmethod
    def from_env(cls) -> 'Config':
        return cls.get_instance()
    
    # Delegate properties to CloudflareConfig
    def __getattr__(self, name: str):
        if self._cf_config and hasattr(self._cf_config, name):
            return getattr(self._cf_config, name)
        raise AttributeError(f"'Config' object has no attribute '{name}'")
    
    # Explicit properties for type checking
    @property
    def google_cloud_project_id(self) -> str:
        return self._cf_config.google_cloud_project_id
    
    @property
    def google_api_key(self) -> str:
        return self._cf_config.google_api_key
    
    @property
    def gemini_api_key(self) -> str:
        return self._cf_config.gemini_api_key
    
    @property
    def encryption_key(self) -> str:
        return self._cf_config.encryption_key
    
    @property
    def environment(self) -> str:
        return self._cf_config.environment
    
    @property
    def base_url(self) -> str:
        return self._cf_config.base_url
    
    @property
    def cors_origins(self) -> List[str]:
        return self._cf_config.cors_origins
    
    @property
    def max_file_size_mb(self) -> int:
        return self._cf_config.max_file_size_mb
    
    @property
    def web_upload_max_mb(self) -> int:
        return self._cf_config.web_upload_max_mb
    
    @property
    def pdf_dpi(self) -> int:
        return self._cf_config.pdf_dpi
    
    @property
    def supported_extensions(self) -> List[str]:
        return self._cf_config.supported_extensions
    
    @property
    def default_language(self) -> str:
        return self._cf_config.default_language
    
    @property
    def processor_type(self) -> str:
        return self._cf_config.processor_type
    
    @property
    def gemini_model_name(self) -> str:
        return self._cf_config.gemini_model_name
    
    @property
    def gemini_temperature(self) -> float:
        return self._cf_config.gemini_temperature
    
    @property
    def gemini_max_output_tokens(self) -> int:
        return self._cf_config.gemini_max_output_tokens
    
    @property
    def prompt_layout(self) -> str:
        return self._cf_config.prompt_layout
    
    @prompt_layout.setter
    def prompt_layout(self, value: str) -> None:
        self._cf_config.prompt_layout = value
    
    @property
    def prompt_strict_mode(self) -> bool:
        return self._cf_config.prompt_strict_mode
    
    @prompt_strict_mode.setter
    def prompt_strict_mode(self, value: bool) -> None:
        self._cf_config.prompt_strict_mode = value
    
    @property
    def prompt_has_diagrams(self) -> bool:
        return self._cf_config.prompt_has_diagrams
    
    @prompt_has_diagrams.setter
    def prompt_has_diagrams(self, value: bool) -> None:
        self._cf_config.prompt_has_diagrams = value
    
    @property
    def prompt_low_quality_mode(self) -> bool:
        return self._cf_config.prompt_low_quality_mode
    
    @prompt_low_quality_mode.setter
    def prompt_low_quality_mode(self, value: bool) -> None:
        self._cf_config.prompt_low_quality_mode = value
    
    @property
    def generate_diagram(self) -> bool:
        return self._cf_config.generate_diagram
    
    @property
    def generate_diagram_png(self) -> bool:
        return self._cf_config.generate_diagram_png
    
    @property
    def generate_diagram_markdown(self) -> bool:
        return self._cf_config.generate_diagram_markdown
    
    @property
    def generate_diagram_mermaid(self) -> bool:
        return self._cf_config.generate_diagram_mermaid
    
    @property
    def tts_language_code(self) -> str:
        return self._cf_config.tts_language_code
    
    @property
    def tts_voice_name(self) -> str:
        return self._cf_config.tts_voice_name
    
    @property
    def pii_masking_enabled(self) -> bool:
        return self._cf_config.pii_masking_enabled
    
    @property
    def temp_directory(self) -> Path:
        return self._cf_config.temp_directory
    
    @property
    def output_directory(self) -> Path:
        return self._cf_config.output_directory
    
    @property
    def drive_enabled(self) -> bool:
        return self._cf_config.drive_enabled
    
    @property
    def drive_auto_upload(self) -> bool:
        return self._cf_config.drive_auto_upload
    
    @property
    def drive_share_public(self) -> bool:
        return self._cf_config.drive_share_public
    
    @property
    def drive_folder_id(self) -> str:
        return self._cf_config.drive_folder_id
    
    @property
    def drive_folder_name(self) -> str:
        return self._cf_config.drive_folder_name
    
    @property
    def drive_credentials_path(self) -> str:
        return self._cf_config.drive_credentials_path
    
    def validate(self) -> List[str]:
        """Validate configuration"""
        errors = []
        
        if not self.google_api_key and not self.gemini_api_key:
            errors.append("GOOGLE_API_KEY or GEMINI_API_KEY is required")
        
        if self.max_file_size_mb <= 0:
            errors.append("MAX_FILE_SIZE_MB must be positive")
        
        if self.pdf_dpi <= 0 or self.pdf_dpi > 600:
            errors.append("PDF_DPI must be between 1 and 600")
        
        if not self.supported_extensions:
            errors.append("SUPPORTED_EXTENSIONS is not set")
        
        if self.gemini_temperature < 0 or self.gemini_temperature > 1:
            errors.append("GEMINI_TEMPERATURE must be between 0 and 1")
        
        if self.gemini_max_output_tokens <= 0:
            errors.append("GEMINI_MAX_OUTPUT_TOKENS must be positive")
        
        return errors
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist"""
        self.temp_directory.mkdir(parents=True, exist_ok=True)
        self.output_directory.mkdir(parents=True, exist_ok=True)


# Initialize with bindings if available (for Pages Functions)
def init_cloudflare_config(bindings: CloudflareBindings) -> Config:
    """Initialize config with Cloudflare bindings"""
    CloudflareConfig.set_bindings(bindings)
    return Config.get_instance()


__all__ = ["Config", "CloudflareConfig", "CloudflareBindings", "init_cloudflare_config"]