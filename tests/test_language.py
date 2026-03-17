"""Tests for language detection."""
import pytest

from app.ai.language import detect_language


class TestLanguageDetection:

    def test_detect_bangla(self):
        assert detect_language("আপনাদের কি কি প্রোডাক্ট আছে?") == "bangla"

    def test_detect_bangla_mixed(self):
        assert detect_language("এই product টা কত?") == "bangla"

    def test_detect_banglish(self):
        assert detect_language("ami ei product ta kinte chai") == "banglish"

    def test_detect_banglish_with_common_words(self):
        assert detect_language("bhai eta koto taka lagbe?") == "banglish"

    def test_detect_banglish_delivery(self):
        assert detect_language("dhaka te delivery kobe pabo?") == "banglish"

    def test_detect_english(self):
        assert detect_language("What products do you have?") == "english"

    def test_detect_english_formal(self):
        assert detect_language("I would like to buy the cotton saree please.") == "english"

    def test_detect_empty_string(self):
        assert detect_language("") == "english"

    def test_detect_numbers_only(self):
        assert detect_language("12345") == "english"

    def test_detect_short_banglish(self):
        assert detect_language("price koto?") == "banglish"
