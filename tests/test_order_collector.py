"""Tests for order data extraction from AI responses."""
import pytest

from app.ai.order_collector import (
    clean_response_for_customer,
    extract_order_from_response,
)


class TestOrderCollector:

    def test_extract_order_from_json_block(self):
        response = '''Great! Your order is confirmed!

```json
{"action": "create_order", "order_data": {
  "product_name": "Cotton Saree",
  "quantity": 2,
  "customer_name": "Fatima Begum",
  "customer_phone": "01712345678",
  "division": "Dhaka",
  "district": "Dhaka",
  "upazila": "Dhanmondi",
  "address_detail": "House 5, Road 10",
  "payment_method": "cod"
}}
```'''
        order = extract_order_from_response(response)
        assert order is not None
        assert order["product_name"] == "Cotton Saree"
        assert order["quantity"] == 2
        assert order["customer_name"] == "Fatima Begum"
        assert order["payment_method"] == "cod"

    def test_extract_order_missing_fields(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Saree",
  "customer_name": "Test"
}}
```'''
        order = extract_order_from_response(response)
        assert order is None  # Missing required fields

    def test_extract_order_invalid_phone(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Saree",
  "customer_name": "Test",
  "customer_phone": "12345",
  "division": "Dhaka",
  "district": "Dhaka",
  "address_detail": "House 1"
}}
```'''
        order = extract_order_from_response(response)
        assert order is None  # Invalid phone

    def test_extract_no_order(self):
        response = "Our Cotton Saree costs ৳1200. Would you like to order?"
        order = extract_order_from_response(response)
        assert order is None

    def test_clean_response_removes_json(self):
        response = '''Your order is confirmed! Thank you!

```json
{"action": "create_order", "order_data": {"product_name": "Saree"}}
```'''
        cleaned = clean_response_for_customer(response)
        assert "json" not in cleaned
        assert "create_order" not in cleaned
        assert "order is confirmed" in cleaned

    def test_clean_response_no_json(self):
        response = "Hello! How can I help you?"
        cleaned = clean_response_for_customer(response)
        assert cleaned == response

    def test_extract_order_defaults(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Silk Punjabi",
  "customer_name": "Rahim",
  "customer_phone": "01812345678",
  "division": "Chittagong",
  "district": "Chittagong",
  "address_detail": "Agrabad C/A"
}}
```'''
        order = extract_order_from_response(response)
        assert order is not None
        assert order["quantity"] == 1  # Default
        assert order["payment_method"] == "cod"  # Default
