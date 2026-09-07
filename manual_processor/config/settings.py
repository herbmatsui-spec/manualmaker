"""
Pydantic settings models for Manual Processor configuration.
Provides type-safe configuration with validation.
"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AppSettings(BaseModel):
    """Application settings"""
    model_config = ConfigDict(extra="ignore")
    
    name: str = "manual-processor"
    version: str = "2.1.0"
    debug: bool = False


class PathSettings(BaseModel):
    """Path settings"""
    model_config = ConfigDict(extra="ignore")
    
    output_directory: str = "./output"
    upload_directory: str = "./uploads"
    temp_directory: str = "./temp"
    log_directory: str = "./logs"


class OCRSettings(BaseModel):
    """OCR processing settings"""
    model_config = ConfigDict(extra="ignore")
    
    provider: str = "google_vision"
    batch_size: int = Field(default=4, ge=1, le=32)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_results: int = Field(default=10, ge=1, le=100)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"google_vision", "gemini"}
        if v not in allowed:
            raise ValueError(f"OCR provider must be one of {allowed}")
        return v


class GeminiSettings(BaseModel):
    """Gemini AI settings"""
    model_config = ConfigDict(extra="ignore")
    
    model: str = "gemini-1.5-flash"
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=2048, ge=1, le=8192)


class ProcessingSettings(BaseModel):
    """Processing settings"""
    model_config = ConfigDict(extra="ignore")
    
    chunk_size: int = Field(default=4000, ge=100, le=100000)
    chunk_overlap: int = Field(default=500, ge=0, le=10000)
    processor_type: str = "gemini"
    fallback_enabled: bool = False

    @field_validator("processor_type")
    @classmethod
    def validate_processor_type(cls, v: str) -> str:
        allowed = {"gemini", "local", "hybrid"}
        if v not in allowed:
            raise ValueError(f"Processor type must be one of {allowed}")
        return v


class WebSettings(BaseModel):
    """Web server settings"""
    model_config = ConfigDict(extra="ignore")
    
    host: str = "0.0.0.0"  # nosec B104 - needed for container networking
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"])
    upload_max_mb: int = Field(default=100, ge=1, le=1000)


class PromptSettings(BaseModel):
    """Prompt configuration settings"""
    model_config = ConfigDict(extra="ignore")
    
    layout: str = "horizontal"
    domain_terms: List[str] = Field(default_factory=list)
    has_diagrams: bool = False
    low_quality_mode: bool = False
    strict_mode: bool = True
    custom_rules: List[str] = Field(default_factory=list)
    generate_diagram: bool = True
    generate_diagram_png: bool = True
    generate_diagram_markdown: bool = True
    generate_diagram_mermaid: bool = False

    @field_validator("layout")
    @classmethod
    def validate_layout(cls, v: str) -> str:
        allowed = {"horizontal", "vertical"}
        if v not in allowed:
            raise ValueError(f"Layout must be one of {allowed}")
        return v


class TTSSettings(BaseModel):
    """Text-to-speech settings"""
    model_config = ConfigDict(extra="ignore")
    
    language_code: str = "ja-JP"
    voice_name: str = "ja-JP-Standard-A"
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-20.0, le=20.0)


class PIISettings(BaseModel):
    """PII masking settings"""
    model_config = ConfigDict(extra="ignore")
    
    enabled: bool = False
    patterns_file: str = "config/pii_patterns.yaml"


class AuditSettings(BaseModel):
    """Audit logging settings"""
    model_config = ConfigDict(extra="ignore")
    
    enabled: bool = True
    retention_days: int = Field(default=90, ge=1, le=365)


class EncryptionSettings(BaseModel):
    """Encryption settings"""
    model_config = ConfigDict(extra="ignore")
    
    key_env: str = "ENCRYPTION_KEY"


class SecuritySettings(BaseModel):
    """Security settings"""
    model_config = ConfigDict(extra="ignore")
    
    pii_masking: PIISettings = Field(default_factory=PIISettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    encryption: EncryptionSettings = Field(default_factory=EncryptionSettings)


class USBSettings(BaseModel):
    """USB monitoring settings"""
    model_config = ConfigDict(extra="ignore")
    
    auto_detect: bool = True
    poll_interval: int = Field(default=5, ge=1, le=60)
    paths: List[str] = Field(default_factory=list)


class GoogleDriveSettings(BaseModel):
    """Google Drive integration settings"""
    model_config = ConfigDict(extra="ignore")
    
    enabled: bool = False
    auto_upload: bool = False
    share_public: bool = True
    folder_id: Optional[str] = None
    folder_name: str = "ManualMaker"
    credentials_path: Optional[str] = None
    token_keyring_service: str = "manual-processor"


class Settings(BaseModel):
    """Root settings model"""
    model_config = ConfigDict(extra="ignore")
    
    app: AppSettings = Field(default_factory=AppSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    prompt: PromptSettings = Field(default_factory=PromptSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    usb: USBSettings = Field(default_factory=USBSettings)
    drive: GoogleDriveSettings = Field(default_factory=GoogleDriveSettings)
