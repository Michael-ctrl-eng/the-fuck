"""Tests for BD phone number validation and normalization."""
import pytest

from app.utils.phone import normalize_bd_phone, validate_bd_phone


class TestPhoneValidation:

    def test_valid_grameenphone(self):
        assert validate_bd_phone("01711234567") is True

    def test_valid_robi(self):
        assert validate_bd_phone("01811234567") is True

    def test_valid_banglalink(self):
        assert validate_bd_phone("01911234567") is True

    def test_valid_teletalk(self):
        assert validate_bd_phone("01511234567") is True

    def test_valid_airtel(self):
        assert validate_bd_phone("01611234567") is True

    def test_valid_with_country_code(self):
        assert validate_bd_phone("8801711234567") is True

    def test_valid_with_plus_country_code(self):
        assert validate_bd_phone("+8801711234567") is True

    def test_valid_with_spaces(self):
        assert validate_bd_phone("017 1123 4567") is True

    def test_valid_with_dashes(self):
        assert validate_bd_phone("017-1123-4567") is True

    def test_invalid_too_short(self):
        assert validate_bd_phone("0171123456") is False

    def test_invalid_too_long(self):
        assert validate_bd_phone("017112345678") is False

    def test_invalid_wrong_prefix(self):
        assert validate_bd_phone("02112345678") is False

    def test_invalid_not_starting_with_01(self):
        assert validate_bd_phone("12345678901") is False

    def test_invalid_empty(self):
        assert validate_bd_phone("") is False

    def test_normalize_with_country_code(self):
        assert normalize_bd_phone("8801711234567") == "01711234567"

    def test_normalize_with_plus(self):
        assert normalize_bd_phone("+8801711234567") == "01711234567"

    def test_normalize_already_normalized(self):
        assert normalize_bd_phone("01711234567") == "01711234567"

    def test_normalize_with_spaces(self):
        assert normalize_bd_phone("017 1123 4567") == "01711234567"
