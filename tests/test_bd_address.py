"""Tests for BD address validation."""
import pytest

from app.utils.bd_address import (
    find_division_for_district,
    get_districts,
    get_divisions,
    get_upazilas,
    validate_address,
)


class TestBDAddress:

    def test_get_all_divisions(self):
        divisions = get_divisions()
        assert len(divisions) == 8
        assert "Dhaka" in divisions
        assert "Chittagong" in divisions
        assert "Rajshahi" in divisions
        assert "Khulna" in divisions
        assert "Barisal" in divisions
        assert "Sylhet" in divisions
        assert "Rangpur" in divisions
        assert "Mymensingh" in divisions

    def test_get_districts_dhaka(self):
        districts = get_districts("Dhaka")
        assert "Dhaka" in districts
        assert "Gazipur" in districts
        assert "Narayanganj" in districts

    def test_get_districts_invalid_division(self):
        assert get_districts("InvalidDivision") == []

    def test_get_upazilas_dhaka(self):
        upazilas = get_upazilas("Dhaka", "Dhaka")
        assert "Dhanmondi" in upazilas
        assert "Gulshan" in upazilas
        assert "Uttara" in upazilas

    def test_get_upazilas_coxs_bazar(self):
        upazilas = get_upazilas("Chittagong", "Cox's Bazar")
        assert "Cox's Bazar Sadar" in upazilas
        assert "Teknaf" in upazilas

    def test_validate_address_valid(self):
        assert validate_address("Dhaka", "Dhaka", "Dhanmondi") is True

    def test_validate_address_valid_no_upazila(self):
        assert validate_address("Dhaka", "Dhaka") is True

    def test_validate_address_invalid_division(self):
        assert validate_address("Invalid", "Dhaka") is False

    def test_validate_address_invalid_district(self):
        assert validate_address("Dhaka", "Invalid") is False

    def test_validate_address_invalid_upazila(self):
        assert validate_address("Dhaka", "Dhaka", "Invalid") is False

    def test_validate_address_district_wrong_division(self):
        """Test that Sylhet is not in Dhaka division."""
        assert validate_address("Dhaka", "Sylhet") is False

    def test_find_division_for_district(self):
        assert find_division_for_district("Dhaka") == "Dhaka"
        assert find_division_for_district("Cox's Bazar") == "Chittagong"
        assert find_division_for_district("Sylhet") == "Sylhet"

    def test_find_division_for_district_case_insensitive(self):
        assert find_division_for_district("dhaka") == "Dhaka"

    def test_find_division_for_unknown_district(self):
        assert find_division_for_district("UnknownPlace") is None
