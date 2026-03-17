from __future__ import annotations

import json
import re
import logging

from app.utils.phone import validate_bd_phone

logger = logging.getLogger(__name__)


def extract_order_from_response(response_text: str) -> dict | None:
    """Extract order JSON from AI response if present."""
    # Look for JSON block in response
    json_match = re.search(
        r'```json\s*(\{.*?\})\s*```',
        response_text,
        re.DOTALL,
    )
    if not json_match:
        # Try without code block
        json_match = re.search(
            r'\{"action":\s*"create_order".*?\}}\s*\}',
            response_text,
            re.DOTALL,
        )

    if not json_match:
        return None

    try:
        data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
        if data.get("action") == "create_order":
            order_data = data.get("order_data", {})
            return validate_order_data(order_data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse order JSON: {e}")

    return None


def validate_order_data(data: dict) -> dict | None:
    """Validate extracted order data. Returns validated data or None."""
    required_fields = [
        "product_name",
        "customer_name",
        "customer_phone",
        "division",
        "district",
        "address_detail",
    ]

    for field in required_fields:
        if not data.get(field):
            logger.warning(f"Missing required order field: {field}")
            return None

    # Validate phone
    phone = data["customer_phone"]
    if not validate_bd_phone(phone):
        logger.warning(f"Invalid BD phone number: {phone}")
        return None

    # Set defaults
    data.setdefault("quantity", 1)
    data.setdefault("payment_method", "cod")
    data.setdefault("upazila", "")

    return data


def clean_response_for_customer(response_text: str) -> str:
    """Remove the JSON block from response before sending to customer."""
    # Remove JSON code blocks
    cleaned = re.sub(r'```json\s*\{.*?\}\s*```', '', response_text, flags=re.DOTALL)
    # Remove inline JSON blocks
    cleaned = re.sub(
        r'\{"action":\s*"create_order".*?\}}\s*\}',
        '',
        cleaned,
        flags=re.DOTALL,
    )
    return cleaned.strip()
