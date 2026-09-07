# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-09-07

### Added

#### USB Auto-Loading (Steps 1-12)
- Added watchdog library integration for file system monitoring
- Implemented USBFileHandler for event-driven file detection
- Added fallback polling mode when watchdog unavailable
- Added USB removal detection
- Added configurable polling interval (`USB_POLL_INTERVAL`)

#### Internationalization (Steps 13-22)
- Added support for 5 languages: Japanese, English, Chinese, Korean, Spanish
- Enhanced language detection with Unicode range analysis
- Added Web API endpoints for i18n:
  - `GET /api/i18n/languages` - List available languages
  - `POST /api/i18n/set` - Set current language
  - `GET /api/i18n/translations/{lang}` - Get translations
  - `POST /api/i18n/detect` - Detect text language
- Added `default_language` config option

#### Output Templates (Steps 23-34)
- Added JSON-based template system for PDF and Word output
- Created default and compact templates for PDF
- Created default and compact templates for Word documents
- Implemented TemplateLoader with inheritance support
- Implemented template validation
- Added `template_name` parameter to `create_formatted_pdf()` and `create_word_document()`

#### Security & Privacy (Steps 35-44)
- Added additional PII patterns: My Number, Passport, Bank Account
- Enhanced `mask_sensitive_data()` with position tracking
- Added `unmask_data()` function for data restoration
- Added Fernet encryption utilities (`encrypt_data()`, `decrypt_data()`)
- Added `secure_delete()` for secure file deletion
- Added AuditLogger for security event logging
- Added GDPRManager for GDPR compliance (export/delete user data)
- Added Web API endpoints:
  - `GET /api/security/status` - Security status
  - `GET /api/security/audit` - Audit logs
  - `POST /api/security/mask` - Mask text

#### Packaging & Distribution (Steps 45-52)
- Added `pyproject.toml` with proper package configuration
- Added `__version__ = "2.1.0"` to package
- Added GitHub Actions workflow for CI/CD
- Added release script (`scripts/release.sh`)
- Added checksum generator (`scripts/checksum.py`)
- Added `.env.example` for environment configuration

### Changed

- Updated `requirements.txt` to include `watchdog>=4.0.0`
- Improved template loading with caching
- Enhanced error messages for template validation

### Fixed

- Fixed `_is_file_locked()` NameError when win32file not available on Linux
- Fixed PII pattern ordering to prevent conflicts (My Number vs Postal code)

## [2.0.0] - Previous Release

### Added
- FastAPI web interface
- GUI application with Tkinter
- Gemini API integration
- PDF, Word, Audio, and Diagram generation
- Batch processing
- USB monitoring
- Progress tracking and cancellation
- Security manager with PII masking
- i18n support (basic)
- Template system (basic)

---

## Version History

- **2.1.0** - Current release with enhanced features
- **2.0.0** - Major release with web UI and GUI
- **1.x.x** - Initial releases
