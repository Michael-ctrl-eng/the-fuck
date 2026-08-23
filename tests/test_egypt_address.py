"""Tests for Egyptian address validation."""
import pytest

from app.utils.egypt_address import (
    GOVERNORATES,
    calculate_shipping,
    find_governorate_for_city,
    get_areas_for_governorate,
    get_cities,
    get_governorates,
    validate_egyptian_address,
)


class TestEgyptAddress:
    def test_exactly_27_governorates(self):
        gov = get_governorates()
        assert len(gov) == 27
        assert "cairo" in gov and "giza" in gov and "alexandria" in gov
        assert "dakahlia" in gov

    def test_cities_returns_arabic_name(self):
        cities = get_cities("cairo")
        assert cities == ["القاهرة"]

    def test_cities_invalid_governorate(self):
        assert get_cities("invalid") == []

    def test_areas_cairo_nonempty(self):
        areas = get_areas_for_governorate("cairo")
        assert len(areas) > 10
        assert "المعادي" in areas

    def test_areas_invalid_governorate(self):
        assert get_areas_for_governorate("invalid") == []

    def test_validate_governorate_only_valid(self):
        assert validate_egyptian_address("cairo") is True

    def test_validate_governorate_only_invalid(self):
        assert validate_egyptian_address("invalid_governorate") is False

    def test_validate_with_known_area(self):
        assert validate_egyptian_address("cairo", "المعادي") is True

    def test_validate_with_unknown_area(self):
        assert validate_egyptian_address("cairo", "القاهرة الكبرى جدا") is False

    def test_find_governorate_by_area(self):
        assert find_governorate_for_city("المعادي") == "cairo"
        assert find_governorate_for_city("سيدي جابر") == "alexandria"

    def test_shipping_inside_zone(self):
        r = calculate_shipping("cairo", 100)
        assert r["cost"] == 35
        assert r["free"] is False

    def test_shipping_outside_zone(self):
        r = calculate_shipping("alexandria", 100)
        assert r["cost"] == 50

    def test_shipping_free_above_threshold(self):
        r = calculate_shipping("cairo", 500)
        assert r["cost"] == 0
        assert r["free"] is True

    def test_shipping_unknown_falls_back_outside_default(self):
        r = calculate_shipping("atlantis", 100)
        assert r["cost"] == 60
        assert r["free"] is False

    def test_every_governorate_has_required_fields(self):
        for key, info in GOVERNORATES.items():
            assert "name_ar" in info, key
            assert "zone" in info, key
            assert "shipping_cost" in info, key
            assert "free_threshold" in info, key

    def test_zones_consistent(self):
        assert GOVERNORATES["cairo"]["zone"] == 1
        assert GOVERNORATES["giza"]["zone"] == 1
        zone_one = [k for k, v in GOVERNORATES.items() if v["zone"] == 1]
        assert set(zone_one) == {"cairo", "giza"}
