import re


def validate_bd_phone(phone: str) -> bool:
    """Validate a Bangladeshi phone number.

    Valid formats:
    - 01XXXXXXXXX (11 digits, starts with 01)
    - +8801XXXXXXXXX
    - 8801XXXXXXXXX
    """
    # Remove spaces, dashes, and parentheses
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)

    # Check various formats
    if re.match(r'^01[3-9]\d{8}$', cleaned):
        return True
    if re.match(r'^8801[3-9]\d{8}$', cleaned):
        return True

    return False


def normalize_bd_phone(phone: str) -> str:
    """Normalize a BD phone number to 01XXXXXXXXX format."""
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)

    if cleaned.startswith("880"):
        cleaned = "0" + cleaned[3:]

    return cleaned
