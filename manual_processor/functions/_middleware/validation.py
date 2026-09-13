"""
Input Validation for Pages Functions API
Provides validation decorators and schemas for all endpoints
"""

import re
import json
from typing import Any, Dict, List, Optional, Callable
from functools import wraps
from dataclasses import dataclass, field


# Validation error class
class ValidationError(Exception):
    def __init__(self, message: str, field: str = None, code: str = "VALIDATION_ERROR"):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


@dataclass
class ValidationResult:
    """Result of validation"""
    valid: bool
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_error(self, field: str, message: str, code: str = "VALIDATION_ERROR"):
        self.valid = False
        self.errors.append({"field": field, "message": message, "code": code})
    
    def to_response(self):
        """Convert to error response format"""
        if self.valid:
            return None
        return {
            "status": 400,
            "errors": self.errors
        }


# =============================================================================
# Base Validators
# =============================================================================

def validate_required(data: Dict, fields: List[str]) -> ValidationResult:
    """Validate required fields exist"""
    result = ValidationResult(valid=True)
    for field_name in fields:
        if field_name not in data or data[field_name] is None or data[field_name] == "":
            result.add_error(field_name, f"Field '{field_name}' is required")
    return result


def validate_string(data: Dict, field: str, min_len: int = 0, max_len: int = None, pattern: str = None) -> ValidationResult:
    """Validate string field"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    if not isinstance(value, str):
        result.add_error(field, f"Field '{field}' must be a string")
        return result
    
    if len(value) < min_len:
        result.add_error(field, f"Field '{field}' must be at least {min_len} characters")
    
    if max_len and len(value) > max_len:
        result.add_error(field, f"Field '{field}' must be at most {max_len} characters")
    
    if pattern and not re.match(pattern, value):
        result.add_error(field, f"Field '{field}' has invalid format")
    
    return result


def validate_number(data: Dict, field: str, min_val: float = None, max_val: float = None, integer: bool = False) -> ValidationResult:
    """Validate numeric field"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    if integer:
        try:
            value = int(value)
        except (ValueError, TypeError):
            result.add_error(field, f"Field '{field}' must be an integer")
            return result
    else:
        try:
            value = float(value)
        except (ValueError, TypeError):
            result.add_error(field, f"Field '{field}' must be a number")
            return result
    
    if min_val is not None and value < min_val:
        result.add_error(field, f"Field '{field}' must be at least {min_val}")
    
    if max_val is not None and value > max_val:
        result.add_error(field, f"Field '{field}' must be at most {max_val}")
    
    return result


def validate_boolean(data: Dict, field: str) -> ValidationResult:
    """Validate boolean field"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    if not isinstance(value, bool):
        result.add_error(field, f"Field '{field}' must be a boolean")
    
    return result


def validate_enum(data: Dict, field: str, allowed: List[str]) -> ValidationResult:
    """Validate enum field"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    if value not in allowed:
        result.add_error(field, f"Field '{field}' must be one of: {', '.join(allowed)}")
    
    return result


def validate_file_id(data: Dict, field: str = "file_id") -> ValidationResult:
    """Validate file ID (hex string)"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    if not isinstance(value, str) or not re.match(r'^[a-f0-9]{32}$', value):
        result.add_error(field, f"Field '{field}' must be a valid 32-character hex string")
    
    return result


def validate_file_type(data: Dict, field: str = "file_type") -> ValidationResult:
    """Validate file type for download"""
    result = ValidationResult(valid=True)
    value = data.get(field)
    
    if value is None:
        return result
    
    allowed = ["pdf", "docx", "audio", "diagram", "diagram_markdown", "diagram_mermaid", "qr", "all"]
    if value not in allowed:
        result.add_error(field, f"Field '{field}' must be one of: {', '.join(allowed)}")
    
    return result


# =============================================================================
# Endpoint-specific Validators
# =============================================================================

def validate_upload_request(data: Dict) -> ValidationResult:
    """Validate file upload request (multipart handled separately)"""
    result = ValidationResult(valid=True)
    # File validation is done in handler (multipart)
    return result


def validate_process_request(data: Dict) -> ValidationResult:
    """Validate PDF processing options"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_boolean(data, "compact_layout").errors)
    result.errors.extend(validate_boolean(data, "use_emojis").errors)
    result.errors.extend(validate_boolean(data, "prompt_strict_mode").errors)
    result.errors.extend(validate_boolean(data, "prompt_has_diagrams").errors)
    result.errors.extend(validate_boolean(data, "prompt_low_quality_mode").errors)
    result.errors.extend(validate_enum(data, "prompt_layout", ["horizontal", "vertical"]).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_mermaid_validate_request(data: Dict) -> ValidationResult:
    """Validate Mermaid validation request"""
    result = ValidationResult(valid=True)
    result.errors.extend(validate_required(data, ["mermaid_code"]).errors)
    result.errors.extend(validate_string(data, "mermaid_code", min_len=1, max_len=50000).errors)
    result.valid = len(result.errors) == 0
    return result


def validate_mermaid_render_request(data: Dict) -> ValidationResult:
    """Validate Mermaid render request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["mermaid_code"]).errors)
    result.errors.extend(validate_string(data, "mermaid_code", min_len=1, max_len=50000).errors)
    result.errors.extend(validate_enum(data, "theme", ["default", "dark", "forest", "neutral"]).errors)
    result.errors.extend(validate_number(data, "width", min_val=100, max_val=2000, integer=True).errors)
    result.errors.extend(validate_number(data, "height", min_val=100, max_val=2000, integer=True).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_mermaid_regenerate_request(data: Dict) -> ValidationResult:
    """Validate Mermaid regenerate request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["current_code", "instruction"]).errors)
    result.errors.extend(validate_string(data, "current_code", min_len=1, max_len=50000).errors)
    result.errors.extend(validate_string(data, "instruction", min_len=1, max_len=2000).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_mermaid_save_request(data: Dict) -> ValidationResult:
    """Validate Mermaid save request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["mermaid_code"]).errors)
    result.errors.extend(validate_string(data, "mermaid_code", min_len=1, max_len=50000).errors)
    result.errors.extend(validate_enum(data, "theme", ["default", "dark", "forest", "neutral"]).errors)
    result.errors.extend(validate_number(data, "width", min_val=100, max_val=2000, integer=True).errors)
    result.errors.extend(validate_number(data, "height", min_val=100, max_val=2000, integer=True).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_drive_upload_request(data: Dict) -> ValidationResult:
    """Validate Drive upload request (empty body allowed)"""
    return ValidationResult(valid=True)


def validate_i18n_set_request(data: Dict) -> ValidationResult:
    """Validate i18n language set request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["language"]).errors)
    result.errors.extend(validate_string(data, "language", min_len=2, max_len=10).errors)
    result.errors.extend(validate_enum(data, "language", ["ja", "en", "zh", "ko", "es", "fr", "de"]).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_i18n_detect_request(data: Dict) -> ValidationResult:
    """Validate i18n language detect request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["text"]).errors)
    result.errors.extend(validate_string(data, "text", min_len=1, max_len=10000).errors)
    
    result.valid = len(result.errors) == 0
    return result


def validate_security_mask_request(data: Dict) -> ValidationResult:
    """Validate security mask request"""
    result = ValidationResult(valid=True)
    
    result.errors.extend(validate_required(data, ["text"]).errors)
    result.errors.extend(validate_string(data, "text", min_len=0, max_len=100000).errors)
    
    result.valid = len(result.errors) == 0
    return result


# =============================================================================
# Validation Decorator
# =============================================================================

def validate_request(validator: Callable[[Dict], ValidationResult]):
    """Decorator to validate request body"""
    def decorator(handler: Callable):
        @wraps(handler)
        async def wrapper(request, env, ctx):
            try:
                # Parse JSON body
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                
                # Validate
                result = validator(body)
                if not result.valid:
                    return {
                        "status": 400,
                        "headers": {"Content-Type": "application/json"},
                        "body": json.dumps({
                            "error": "Validation failed",
                            "details": result.errors
                        }, ensure_ascii=False)
                    }
                
                # Attach validated data to request for handler
                request._validated_data = result.data
                
                return await handler(request, env, ctx)
            except ValidationError as e:
                return {
                    "status": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": e.message,
                        "field": e.field,
                        "code": e.code
                    }, ensure_ascii=False)
                }
            except Exception as e:
                # Let handler handle other errors
                return await handler(request, env, ctx)
        return wrapper
    return decorator


# =============================================================================
# Query Parameter Validators
# =============================================================================

def validate_query_params(required: List[str] = None, optional: Dict[str, Dict] = None):
    """Validate query parameters"""
    def decorator(handler: Callable):
        @wraps(handler)
        async def wrapper(request, env, ctx):
            from functions._middleware import get_query_params
            
            params = get_query_params(request)
            errors = []
            
            # Check required
            if required:
                for field in required:
                    if field not in params:
                        errors.append({"field": field, "message": f"Query parameter '{field}' is required"})
            
            # Validate optional with rules
            if optional:
                for field, rules in optional.items():
                    if field in params:
                        value = params[field]
                        if "type" in rules:
                            if rules["type"] == "int":
                                try:
                                    value = int(value)
                                    if "min" in rules and value < rules["min"]:
                                        errors.append({"field": field, "message": f"'{field}' must be at least {rules['min']}"})
                                    if "max" in rules and value > rules["max"]:
                                        errors.append({"field": field, "message": f"'{field}' must be at most {rules['max']}"})
                                except ValueError:
                                    errors.append({"field": field, "message": f"'{field}' must be an integer"})
                            elif rules["type"] == "float":
                                try:
                                    value = float(value)
                                    if "min" in rules and value < rules["min"]:
                                        errors.append({"field": field, "message": f"'{field}' must be at least {rules['min']}"})
                                    if "max" in rules and value > rules["max"]:
                                        errors.append({"field": field, "message": f"'{field}' must be at most {rules['max']}"})
                                except ValueError:
                                    errors.append({"field": field, "message": f"'{field}' must be a number"})
                            elif rules["type"] == "enum":
                                if value not in rules.get("values", []):
                                    errors.append({"field": field, "message": f"'{field}' must be one of: {', '.join(rules['values'])}"})
            
            if errors:
                return {
                    "status": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Query validation failed", "details": errors}, ensure_ascii=False)
                }
            
            request._query_params = params
            return await handler(request, env, ctx)
        return wrapper
    return decorator