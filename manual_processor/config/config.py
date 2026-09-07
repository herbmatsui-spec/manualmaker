import os
import logging
from pathlib import Path
from typing import List, Optional, ClassVar
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _safe_int(env_key: str, default: int) -> int:
    """環境変数を安全に int に変換"""
    value = os.getenv(env_key, str(default))
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"環境変数 {env_key}='{value}' は整数ではありません。デフォルト値 {default} を使用します。")
        return default


def _safe_float(env_key: str, default: float) -> float:
    """環境変数を安全に float に変換"""
    value = os.getenv(env_key, str(default))
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(f"環境変数 {env_key}='{value}' は数値ではありません。デフォルト値 {default} を使用します。")
        return default


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables"""
    _instance: ClassVar[Optional['AppConfig']] = None
    
    # Google Cloud設定
    google_cloud_project_id: str
    vision_api: bool  # Whether to use Vision API (True) or fallback to Gemini for OCR (False)
    google_application_credentials: str  # Path to service account JSON
    
    # OCR設定
    vision_api_timeout: int = 30
    vision_max_results: int = 10
    
    # Gemini設定
    gemini_model_name: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.3
    gemini_max_output_tokens: int = 2048

    # チャンク処理設定 (ステップ 9)
    chunk_size: int = 4000
    chunk_overlap: int = 500

    # プロセッサー選択設定 (ステップ 10)
    processor_type: str = "gemini"  # gemini, local, hybrid
    fallback_enabled: bool = True

    # Web UI 設定 (Phase 2)
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    web_cors_origins: List[str] = field(default_factory=lambda: ["*"])
    web_upload_max_mb: int = 100

    # 手書き文字起こしプロンプト設定
    prompt_layout: str = "horizontal"
    prompt_domain_terms: List[str] = field(default_factory=list)
    prompt_has_diagrams: bool = False
    prompt_low_quality_mode: bool = False
    prompt_strict_mode: bool = True
    prompt_custom_rules: List[str] = field(default_factory=list)
    generate_diagram: bool = True


    
    # 音声合成設定
    tts_language_code: str = "ja-JP"
    tts_voice_name: str = "ja-JP-Standard-A"
    tts_speaking_rate: float = 1.0
    tts_pitch: float = 0.0
    
    # ファイルパス設定
    usb_monitor_paths: List[str] = field(default_factory=list)  # 監視するUSBドライブパスリスト
    usb_auto_detect: bool = True  # USB自動検出有効/無効
    usb_poll_interval: float = 1.0  # polling間隔（秒）

    # i18n設定
    default_language: str = "ja"  # デフォルト言語
    output_directory: Path = field(default_factory=lambda: Path("./output"))
    temp_directory: Path = field(default_factory=lambda: Path("./temp"))
    
    #  処理設定
    pdf_dpi: int = 300  # PDFから画像への変換DPI
    max_file_size_mb: int = 50  #  処理可能な最大ファイルサイズ
    supported_extensions: List[str] = field(default_factory=lambda: [".pdf"])
    
    def __post_init__(self):
        """初期化後の処理"""
        if self.supported_extensions is None:
            self.supported_extensions = ['.pdf']
        if self.usb_monitor_paths is None:
            self.usb_monitor_paths = []
    
    # Backward compatibility properties
    @property
    def google_api_key(self) -> str:
        """Backward compatibility: returns empty string (Vision API uses service account or ADC)"""
        # For backward compatibility with existing code that expects this field
        # In practice, when using Vision API with service account, this is not used
        # But we return empty string to avoid breaking existing code
        return ""
    
    @property
    def gemini_api_key(self) -> str:
        """Backward compatibility: returns empty string - actual key should be obtained from ADC or env"""
        # For backward compatibility with existing code
        # The actual Gemini API key should be obtained from Application Default Credentials
        # or environment variables in the gemini_summarizer module
        return ""
    
    @property
    def ocr_model(self) -> str:
        """Backward compatibility"""
        return "gemini-1.5-flash" if not self.vision_api else "vision-api"
    
    @property
    def summary_model(self) -> str:
        """Backward compatibility"""
        return self.gemini_model_name
    
    @property
    def tts_model(self) -> str:
        """Backward compatibility"""
        return "gemini-2.5-flash-tts"  # Keep existing default
    
    @property
    def tts_fallback_model(self) -> str:
        """Backward compatibility"""
        return "gemini-3.1-flash-tts"  # Keep existing default
    
    @property
    def compact_layout(self) -> bool:
        """Backward compatibility"""
        return False
    
    @property
    def use_emojis(self) -> bool:
        """Backward compatibility"""
        return False
    
    @property
    def diagram_theme(self) -> str:
        """Backward compatibility"""
        return "default"
    
    @property
    def diagram_width(self) -> int:
        """Backward compatibility"""
        return 800
    
    @property
    def diagram_height(self) -> int:
        """Backward compatibility"""
        return 600
    
    @classmethod
    def get_instance(cls) -> 'AppConfig':
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls.from_env()
        return cls._instance
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """環境変数から設定を読み込み"""
        # Google Cloud設定
        google_cloud_project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        # Support both VISION_API flag and legacy GOOGLE_API_KEY/GEMINI_API_KEY for OCR
        vision_api_flag = os.getenv("VISION_API", "True").lower() in ("true", "1", "yes")
        # Legacy support: if GOOGLE_API_KEY or GEMINI_API_KEY is set, treat as Vision API enabled
        legacy_ocr_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        vision_api = vision_api_flag or bool(legacy_ocr_key)
        google_application_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        # OCR設定
        vision_api_timeout = _safe_int("VISION_API_TIMEOUT", 30)
        vision_max_results = _safe_int("VISION_MAX_RESULTS", 10)
        
        # Gemini設定
        gemini_model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        gemini_temperature = _safe_float("GEMINI_TEMPERATURE", 0.3)
        gemini_max_output_tokens = _safe_int("GEMINI_MAX_OUTPUT_TOKENS", 2048)
        
        # 音声合成設定
        tts_language_code = os.getenv("TTS_LANGUAGE_CODE", "ja-JP")
        tts_voice_name = os.getenv("TTS_VOICE_NAME", "ja-JP-Standard-A")
        tts_speaking_rate = _safe_float("TTS_SPEAKING_RATE", 1.0)
        tts_pitch = _safe_float("TTS_PITCH", 0.0)
        
        # ファイルパス設定
        usb_monitor_paths_str = os.getenv("USB_MONITOR_PATHS", "")
        usb_monitor_paths = [p.strip() for p in usb_monitor_paths_str.split(",") if p.strip()] if usb_monitor_paths_str else []
        usb_auto_detect = os.getenv("USB_AUTO_DETECT", "True").lower() in ("true", "1", "yes")
        usb_poll_interval = _safe_float("USB_POLL_INTERVAL", 1.0)
        default_language = os.getenv("APP_LANGUAGE", "ja").lower()
        
        output_dir = os.getenv("OUTPUT_DIRECTORY", "./output")
        temp_dir = os.getenv("TEMP_DIRECTORY", "./temp")
        
        # 処理設定
        pdf_dpi = _safe_int("PDF_DPI", 300)
        max_file_size_mb = _safe_int("MAX_FILE_SIZE_MB", 50)
        supported_extensions_str = os.getenv("SUPPORTED_EXTENSIONS", ".pdf")
        supported_extensions = [ext.strip() for ext in supported_extensions_str.split(",")] if supported_extensions_str else [".pdf"]
        
        # Web UI 設定
        web_host = os.getenv("WEB_HOST", "127.0.0.1")
        web_port = _safe_int("WEB_PORT", 8000)
        web_upload_max_mb = _safe_int("WEB_UPLOAD_MAX_MB", 100)

        prompt_layout = os.getenv("PROMPT_LAYOUT", "horizontal").lower()
        if prompt_layout not in ("horizontal", "vertical"):
            prompt_layout = "horizontal"
        prompt_domain_terms = [
            term.strip()
            for term in os.getenv("PROMPT_DOMAIN_TERMS", "").split(",")
            if term.strip()
        ]
        prompt_has_diagrams = os.getenv("PROMPT_HAS_DIAGRAMS", "False").lower() in ("true", "1", "yes")
        prompt_low_quality_mode = os.getenv("PROMPT_LOW_QUALITY_MODE", "False").lower() in ("true", "1", "yes")
        prompt_strict_mode = os.getenv("PROMPT_STRICT_MODE", "True").lower() in ("true", "1", "yes")
        prompt_custom_rules = [
            rule.strip()
            for rule in os.getenv("PROMPT_CUSTOM_RULES", "").splitlines()
            if rule.strip()
        ]

        return cls(
            google_cloud_project_id=google_cloud_project_id,
            vision_api=vision_api,
            google_application_credentials=google_application_credentials,
            vision_api_timeout=vision_api_timeout,
            vision_max_results=vision_max_results,
            gemini_model_name=gemini_model_name,
            gemini_temperature=gemini_temperature,
            gemini_max_output_tokens=gemini_max_output_tokens,
            web_host=web_host,
            web_port=web_port,
            web_upload_max_mb=web_upload_max_mb,
            prompt_layout=prompt_layout,
            prompt_domain_terms=prompt_domain_terms,
            prompt_has_diagrams=prompt_has_diagrams,
            prompt_low_quality_mode=prompt_low_quality_mode,
            prompt_strict_mode=prompt_strict_mode,
            prompt_custom_rules=prompt_custom_rules,
            tts_language_code=tts_language_code,
            tts_voice_name=tts_voice_name,
            tts_speaking_rate=tts_speaking_rate,
            tts_pitch=tts_pitch,
            usb_monitor_paths=usb_monitor_paths,
            usb_auto_detect=usb_auto_detect,
            usb_poll_interval=usb_poll_interval,
            default_language=default_language,

            output_directory=Path(output_dir),
            temp_directory=Path(temp_dir),
            pdf_dpi=pdf_dpi,
            max_file_size_mb=max_file_size_mb,
            supported_extensions=supported_extensions
        )
    
    def validate(self) -> List[str]:
        """設定の�妥当性を�検�証し、エラーのリストを返す"""
        errors = []
        
        # Google Cloud設定
        if not self.google_cloud_project_id or not self.google_cloud_project_id.strip():
            errors.append("GOOGLE_CLOUD_PROJECT_ID is not set")
        
        # Vision API認�証: サービスアカウントかAPIキーのいずれかが必要
        if self.vision_api:
            has_service_account = bool(self.google_application_credentials and self.google_application_credentials.strip())
            has_legacy_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
            if not (has_service_account or has_legacy_key):
                errors.append("Either GOOGLE_APPLICATION_CREDENTIALS (service account) or GOOGLE_API_KEY/GEMINI_API_KEY is required when VISION_API is enabled")
        
        # Gemini API認�証: Application Default Credentialsまたは環境変数が必要
        # Note: Actual validation happens in gemini_summarizer.py
        
        # OCR設定
        if self.vision_api_timeout <= 0:
            errors.append("VISION_API_TIMEOUT must be positive")
            
        if self.vision_max_results <= 0:
            errors.append("VISION_MAX_RESULTS must be positive")
        
        # Gemini設定
        if not (0.0 <= self.gemini_temperature <= 1.0):
            errors.append("GEMINI_TEMPERATURE must be between 0.0 and 1.0")
            
        if self.gemini_max_output_tokens <= 0:
            errors.append("GEMINI_MAX_OUTPUT_TOKENS must be positive")
        
        # 音声合成設定
        if self.tts_speaking_rate <= 0:
            errors.append("TTS_SPEAKING_RATE must be positive")
        
        # ファイルパス設定
        if not self.output_directory:
            errors.append("OUTPUT_DIRECTORY is not set")
            
        if not self.temp_directory:
            errors.append("TEMP_DIRECTORY is not set")
        
        # � 処理設定
        if self.pdf_dpi <= 0:
            errors.append("PDF_DPI must be positive")
        elif self.pdf_dpi > 600:
            errors.append("PDF_DPI exceeds 600 (may cause memory issues)")
            
        if self.max_file_size_mb <= 0:
            errors.append("MAX_FILE_SIZE_MB must be positive")
        
        if not self.supported_extensions:
            errors.append("SUPPORTED_EXTENSIONS is not set")
        
        return errors
    
    def ensure_directories(self) -> None:
        """出力ディレクトリとテンポラリディレクトリを作成"""
        for dir_path, label in [(self.output_directory, "output"), (self.temp_directory, "temp")]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise ValueError(f"Permission denied for {label} directory: {dir_path}")
            except OSError as e:
                raise ValueError(f"Failed to create {label} directory: {dir_path} ({e})")

Config = AppConfig