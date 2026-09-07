# Release Notes - v2.1.0

**Release Date:** 2026-09-07

---

## Highlights

This release introduces significant enhancements to the Manual Processor system, including:

- **Enhanced USB Auto-Loading** with watchdog integration
- **Expanded Internationalization** supporting 5 languages
- **New Template System** for customizable PDF and Word output
- **Improved Security** with encryption utilities and GDPR compliance

---

## New Features

### USB Auto-Loading (Steps 1-12)
- Real-time file monitoring using watchdog library
- Automatic USB drive detection and removal handling
- Configurable polling interval
- Fallback to polling mode when watchdog unavailable

### Internationalization (Steps 13-22)
- **5 Languages:** Japanese, English, Chinese, Korean, Spanish
- Enhanced Unicode-based language detection
- REST API for dynamic language management
- Language detection endpoint

### Output Templates (Steps 23-34)
- JSON-based template definition for PDF and Word
- Template inheritance (parent/child relationships)
- Default and Compact template presets
- Template validation and caching

### Security & Privacy (Steps 35-44)
- **PII Patterns:** Email, Phone, Postal Code, Credit Card, IP Address, My Number, Passport, Bank Account
- Position-aware masking for unmasking support
- Fernet encryption utilities
- Secure file deletion
- Audit logging system
- GDPR compliance helpers (export/delete user data)

### Packaging & Distribution (Steps 45-52)
- `pyproject.toml` for modern Python packaging
- GitHub Actions CI/CD workflow
- Automated release script
- Checksum generation

### Performance (Steps 53-60)
- Cache manager with TTL support
- Cache statistics and expired entry cleanup
- Benchmark suite

### Integration (Steps 61-72)
- Enhanced exception hierarchy
- Full test suite: **246 tests**
- Documentation updates

---

## Installation

```bash
# Fresh installation
pip install -e .

# Upgrade from v2.0
pip install -r requirements.txt
```

---

## Dependencies

New in v2.1:

```
watchdog>=4.0.0
```

---

## API Changes

### New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/i18n/languages` | GET | List available languages |
| `/api/i18n/set` | POST | Set current language |
| `/api/i18n/translations/{lang}` | GET | Get translations for language |
| `/api/i18n/detect` | POST | Detect text language |
| `/api/security/status` | GET | Get security status |
| `/api/security/audit` | GET | Get audit logs |
| `/api/security/mask` | POST | Mask text PII |

### New Function Parameters

```python
# PDF/Word generation
create_formatted_pdf(content, output, template_name="compact")
create_word_document(content, output, template_name="default")

# Cache manager
CacheManager(cache_dir, max_memory_entries, ttl_seconds=3600)
cache.get_stats()
cache.clear_expired()
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USB_POLL_INTERVAL` | 1.0 | USB polling interval (seconds) |
| `USB_AUTO_DETECT` | true | Enable USB auto-detection |
| `APP_LANGUAGE` | ja | Default application language |

---

## Migration from v2.0

All existing APIs are backwards compatible. No migration steps required.

See [UPGRADE.md](UPGRADE.md) for detailed upgrade instructions.

---

## Known Issues

None.

---

## Contributors

Manual Processor Team

---

## License

MIT License
