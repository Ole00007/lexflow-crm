"""Input validation utilities for LexFlow CRM API"""

def validate_string(value, field_name, min_length=1, max_length=255, required=True):
    """Validate string input"""
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    value = value.strip()
    
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    
    if len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    
    return True, value

def validate_email(email):
    """Validate email format"""
    import re
    if not email:
        return False, "Email is required"
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, str(email)):
        return False, "Invalid email format"
    
    return True, email.strip().lower()

def validate_password(password):
    """Validate password strength"""
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    
    # At least one uppercase, one lowercase, one digit
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "Password must contain uppercase, lowercase, and digit"
    
    return True, password

def validate_integer(value, field_name, min_val=None, max_val=None, required=True):
    """Validate integer input"""
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        return False, f"{field_name} must be an integer"
    
    if min_val is not None and int_val < min_val:
        return False, f"{field_name} must be at least {min_val}"
    
    if max_val is not None and int_val > max_val:
        return False, f"{field_name} must be at most {max_val}"
    
    return True, int_val

def validate_date(value, field_name, required=False):
    """Validate ISO date format"""
    if value is None or value == "":
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    from datetime import datetime
    try:
        date_obj = datetime.fromisoformat(str(value)).date()
        return True, date_obj
    except (ValueError, AttributeError):
        return False, f"{field_name} must be in ISO format (YYYY-MM-DD)"

def validate_enum(value, field_name, allowed_values, required=True):
    """Validate enum value"""
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if value not in allowed_values:
        return False, f"{field_name} must be one of: {', '.join(allowed_values)}"
    
    return True, value

def validate_phone(phone):
    """Validate phone number (basic)"""
    import re
    if not phone:
        return False, "Phone is required"
    
    # Remove common formatting characters
    phone_clean = re.sub(r'[\s\-\(\)\.]+', '', phone)
    
    if not re.match(r'^\+?[1-9]\d{1,14}$', phone_clean):
        return False, "Invalid phone number format"
    
    return True, phone_clean

def validate_request_json(request, required_fields=None):
    """Validate request has JSON and required fields"""
    data = request.get_json()
    
    if not data:
        return False, "Request body must be JSON", None
    
    if required_fields:
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", None
    
    return True, None, data
