"""Tests for prompt generation with flexible product attributes (Arabic output)."""
import pytest

from app.ai.prompts import get_product_context, get_system_prompt


class TestPrompts:

    def test_system_prompt_contains_business_name(self):
        prompt = get_system_prompt("My Store", "No products", "auto")
        assert "My Store" in prompt
        assert "بائع" in prompt  # salesperson persona

    def test_system_prompt_is_egyptian_arabic(self):
        prompt = get_system_prompt("Test", "products", "auto")
        assert "عامية" in prompt or "المصرية" in prompt

    def test_system_prompt_contains_order_instructions(self):
        prompt = get_system_prompt("Test", "products", "auto")
        assert "المحافظة" in prompt or "governorate" in prompt.lower()
        assert "COD" in prompt or "كاش عند التوصيل" in prompt

    def test_product_context_empty(self):
        context = get_product_context([])
        assert "مفيش منتجات" in context

    def test_product_context_with_standard_products(self):
        products = [
            {
                "name": "Cotton Galabiya",
                "name_ar": "جلابية قطن",
                "description": "Premium quality",
                "price": 1500,
                "discount_price": 1200,
                "category": "Clothing",
                "stock_status": "in_stock",
                "material": "cotton",
            },
        ]
        context = get_product_context(products)
        assert "Cotton Galabiya" in context
        assert "1500" in context          # original price struck-through
        assert "1200" in context          # discount price
        assert "ج.م" in context           # EGP currency marker

    def test_product_context_electronics(self):
        """Completely different product format — electronics."""
        products = [
            {
                "name": "Samsung A15",
                "price": 18000,
                "brand": "Samsung",
                "RAM": "6GB",
                "storage": "128GB",
            },
        ]
        context = get_product_context(products)
        assert "Samsung A15" in context
        assert "18000" in context
        assert "ج.م" in context

    def test_product_context_food(self):
        """Food products with weight and flavor."""
        products = [
            {
                "name": "Chocolate Cake",
                "price": 850,
                "flavor": "dark chocolate",
                "weight": "1kg",
                "serves": "8-10",
            },
        ]
        context = get_product_context(products)
        assert "Chocolate Cake" in context
        assert "850" in context

    def test_product_context_lists_each_product(self):
        products = [
            {"name": "P1", "price": 100, "category": "Cat A", "stock_status": "in_stock"},
            {"name": "P2", "price": 200, "category": "Cat B", "stock_status": "in_stock"},
        ]
        context = get_product_context(products)
        assert "P1" in context and "P2" in context
        assert "100" in context and "200" in context

    def test_product_context_out_of_stock_icon(self):
        products = [
            {"name": "Gone Product", "price": 999, "stock_status": "out_of_stock"},
        ]
        context = get_product_context(products)
        assert "Gone Product" in context
        assert "❌" in context

    def test_product_context_no_category(self):
        """Products without category should still render fine."""
        products = [
            {"name": "Random Item", "price": 100},
        ]
        context = get_product_context(products)
        assert "Random Item" in context
        assert "100" in context
