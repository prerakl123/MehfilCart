"""Phone number validation and formatting utilities."""

import re


# Matches Indian phone numbers: optional +91 prefix followed by 10 digits starting with 6-9
_INDIAN_PHONE_REGEX = re.compile(r"^(\+91)?[6-9]\d{9}$")


def is_valid_phone(phone: str) -> bool:
    """Validate an Indian phone number."""
    cleaned = phone.replace(" ", "").replace("-", "")
    return bool(_INDIAN_PHONE_REGEX.match(cleaned))


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to E.164 format (+91XXXXXXXXXX).
    Strips spaces, dashes, and ensures +91 prefix.
    """
    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.startswith("+91"):
        return cleaned
    if cleaned.startswith("91") and len(cleaned) == 12:
        return f"+{cleaned}"
    if len(cleaned) == 10 and cleaned[0] in "6789":
        return f"+91{cleaned}"
    return cleaned  # Return as-is if format is unrecognized
