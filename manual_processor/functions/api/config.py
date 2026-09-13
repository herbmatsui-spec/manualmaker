"""
Pages Functions API Handler - Health & Config
"""

import json
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_request, validate_query_params,
    validate_i18n_set_request, validate_i18n_detect_request
)
from config.config import Config


async def on_request(request, env, ctx):
    """Main entry point for /api/* routes"""
    path = request.url.path
    method = request.method
    
    # Handle CORS preflight
    if method == "OPTIONS":
        return await handle_options(request)
    
    # Route to appropriate handler
    if path == "/api/health":
        return await health_check(request, env, ctx)
    elif path == "/api/config":
        return await get_config(request, env, ctx)
    elif path == "/api/i18n/languages":
        return await get_languages(request, env, ctx)
    elif path.startswith("/api/i18n/translations/"):
        lang = path.split("/")[-1]
        return await get_translations(request, env, ctx, lang)
    elif path == "/api/i18n/set" and method == "POST":
        return await set_language(request, env, ctx)
    elif path == "/api/i18n/detect" and method == "POST":
        return await detect_language(request, env, ctx)
    
    return error_response("Not found", 404)


async def health_check(request, env, ctx):
    """Health check endpoint"""
    config = Config.get_instance()
    return json_response({
        "status": "ok",
        "version": "3.1.0",
        "processor_type": config.processor_type,
        "environment": env.ENVIRONMENT if hasattr(env, 'ENVIRONMENT') else "production"
    })


async def get_config(request, env, ctx):
    """Get public configuration"""
    config = Config.get_instance()
    return json_response({
        "gemini_model_name": config.gemini_model_name,
        "processor_type": config.processor_type,
        "pdf_dpi": config.pdf_dpi,
        "max_file_size_mb": config.max_file_size_mb,
        "web_upload_max_mb": config.web_upload_max_mb,
        "output_directory": str(config.output_directory),
        "supported_extensions": config.supported_extensions,
        "default_language": config.default_language
    })


async def get_languages(request, env, ctx):
    """Get available languages"""
    from src.i18n_manager import I18nManager
    config = Config.get_instance()
    i18n_manager = I18nManager(default_lang=config.default_language)
    
    return json_response({
        "languages": i18n_manager.get_available_languages(),
        "current": i18n_manager.current_lang
    })


async def get_translations(request, env, ctx, lang: str):
    """Get translations for a language"""
    from src.i18n_manager import I18nManager
    config = Config.get_instance()
    i18n_manager = I18nManager(default_lang=config.default_language)
    
    translations = i18n_manager.TRANSLATIONS.get(lang.lower())
    if not translations:
        return error_response(f"Language '{lang}' not found", 404)
    
    return json_response(translations)


@validate_request(validate_i18n_set_request)
async def set_language(request, env, ctx):
    """Set current language"""
    from src.i18n_manager import I18nManager
    config = Config.get_instance()
    i18n_manager = I18nManager(default_lang=config.default_language)
    
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        language = data.get("language", "")
        i18n_manager.set_language(language)
        return json_response({"status": "ok", "language": i18n_manager.current_lang})
    except Exception as e:
        return error_response(f"Invalid request: {str(e)}")


@validate_request(validate_i18n_detect_request)
async def detect_language(request, env, ctx):
    """Detect language from text"""
    from src.i18n_manager import I18nManager
    config = Config.get_instance()
    i18n_manager = I18nManager(default_lang=config.default_language)
    
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        text = data.get("text", "")
        detected = i18n_manager.detect_language(text)
        return json_response({"detected_language": detected})
    except Exception as e:
        return error_response(f"Invalid request: {str(e)}")


async def handle_options(request):
    """Handle OPTIONS preflight"""
    from functions._middleware import cors_headers
    return {
        "status": 204,
        "headers": cors_headers()
    }