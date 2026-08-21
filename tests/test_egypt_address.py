"""Tests for Egyptian address validation."""
import pytest

from app.utils.egypt_address import (
    get_governorates,
    get_cities,
    get_areas_for_governorate,
    validate_egyptian_address,
    calculate_shipping,
)


class TestEgyptAddress:
    def test_get_all_governorates(self):
        gov = get_governorates()
        assert len(gov) == 27
        assert "cairo" in gov
        assert "giza" in gov
        assert "alexandria" in gov

    def test_get_cities_cairo(self):
        cities = get_cities("cairo")
        assert len(cities) > 0
        assert "Cairo" in cities or "cairo" in [c.lower() for c in cities]

    def test_get_cities_invalid_governorate(self):
        cities = get_cities("invalid")
        assert cities == []

    def test_get_areas_cairo(self):
        areas = get_areas_for_governorate("cairo")
        assert len(areas) > 0

    def test_validate_address_valid(self):
        assert validate_egyptian_address("cairo") is True

    def test_validate_address_invalid_governorate(self):
        assert validate_egyptian_address("invalid_governorate") is False

    def test_shipping_inside_cairo(self):
        cost = calculate_shipping("cairo", 100)
        assert cost >= 0

    def test_shipping_outside_cairo(self):
        cost = calculate_shipping("alexandria", 100)
        assert cost >= 0

    def test_free_shipping_above_threshold(self):
        cost = calculate_shipping("cairo", 500)
        assert cost == 0
