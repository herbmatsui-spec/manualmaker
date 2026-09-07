# Upgrade Guide

## Upgrading from v2.0 to v2.1

This guide helps you upgrade from Manual Processor v2.0 to v2.1.

### New Features

#### USB Auto-Loading (Steps 1-12)
- New `watchdog` library integration for real-time file monitoring
- Configurable via `USB_POLL_INTERVAL` environment variable
- Automatic USB drive detection

#### Internationalization (Steps 13-22)
- 5 languages now supported: Japanese, English, Chinese, Korean, Spanish
- New API endpoints for language management
- Enhanced language detection

#### Output Templates (Steps 23-34)
- JSON-based template system for PDF and Word documents
- Template inheritance support
- New `template_name` parameter for `create_formatted_pdf()` and `create_word_document()`

#### Security & Privacy (Steps 35-44)
- Additional PII patterns: My Number, Passport, Bank Account
- Position tracking for masked data
- New encryption utilities (`encrypt_data()`, `decrypt_data()`)
- `AuditLogger` for security event logging
- `GDPRManager` for compliance

### Breaking Changes

None. All existing APIs are backwards compatible.

### New Environment Variables

```env
# USB Monitor (NEW)
USB_POLL_INTERVAL=1.0

# Language (NEW)
APP_LANGUAGE=ja
```

### New Dependencies

```
watchdog>=4.0.0
```

### New API Endpoints

```
GET  /api/i18n/languages
POST /api/i18n/set
GET  /api/i18n/translations/{lang}
POST /api/i18n/detect
GET  /api/security/status
GET  /api/security/audit
POST /api/security/mask
```

### Upgrade Steps

1. Install new dependencies:
```bash
pip install -r requirements.txt
```

2. Update environment variables (optional):
```bash
# Add new variables to .env
USB_POLL_INTERVAL=1.0
APP_LANGUAGE=ja
```

3. Verify installation:
```bash
python -m pytest tests/ -v
```

### Template System

To use the new template system:

```python
from src.pdf_generator import create_formatted_pdf

# Using named template
create_formatted_pdf(
    content,
    output_path,
    template_name="compact"  # or "default"
)
```

### Security Features

```python
from src.security_manager import SecurityManager, AuditLogger

# Mask with position tracking
masked, info = SecurityManager.mask_sensitive_data(text, record_positions=True)

# Audit logging
audit = AuditLogger()
audit.log("user_id", "ACTION", "/resource")
```
