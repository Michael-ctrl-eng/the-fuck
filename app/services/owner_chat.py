"""Owner chat — page owner sends natural language commands to update products/prices/rules."""

import json
import logging
import re

from app.ai.llm_client import chat_completion_with_usage

logger = logging.getLogger(__name__)

OWNER_SYSTEM_PROMPT = """أنت مساعد ذكي لصاحب الصفحة. بيكلمك بالعامية المصرية.
مهمتك تفهم أوامره وتحولها لـ JSON actions.

الأوامر الممكنة:

1. تحديث سعر منتج:
{{"action": "update_price", "product_name": "...", "new_price": 123}}

2. تحديث مخزون:
{{"action": "update_stock", "product_name": "...", "stock_status": "in_stock|out_of_stock|limited"}}

3. إضافة منتج جديد:
{{"action": "add_product", "name": "...", "price": 123, "description": "..."}}

4. حذف منتج:
{{"action": "delete_product", "product_name": "..."}}

5. تحديث رسوم الشحن:
{{"action": "update_shipping", "inside_cairo": 35, "outside_cairo": 60, "free_above": 300}}

6. سؤال عام عن المخزون/الأوامر:
{{"action": "info_request", "query": "..."}}

ممنوع تختلق معلومات. لو مش فاهمsomething اسأله يوضّح.
IMPORTANT: Return ONLY the JSON object, no other text."""


async def parse_owner_instruction(text: str, products: list[dict] | None = None) -> dict | None:
    """Parse owner's natural language instruction into a structured action."""

    products_list = ""
    if products:
        products_list = "\nالمنتجات الحالية:\n" + "\n".join(
            f"- {p['name']}: {p['price']} ج.م" for p in products[:20]
        )

    try:
        result = await chat_completion_with_usage([
            {"role": "system", "content": OWNER_SYSTEM_PROMPT + products_list},
            {"role": "user", "content": text},
        ])
        raw = result.content.strip()

        # Parse JSON
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                return json.loads(m.group(0))
            return None

    except Exception as e:
        logger.error(f"Owner instruction parsing failed: {e}")
        return None


async def execute_owner_action(db, tenant, action: dict) -> str:
    """Execute a parsed owner action and return a confirmation message."""
    from app.models.product import Product
    from sqlalchemy import select
    import uuid

    action_type = action.get("action")

    if action_type == "update_price":
        product_name = action.get("product_name", "")
        new_price = action.get("new_price")
        if not product_name or new_price is None:
            return "محتاج اسم المنتج والسعر الجديد"

        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.name.ilike(f"%{product_name}%"),
            ).limit(1)
        )
        product = result.scalar_one_or_none()
        if not product:
            return f"مش لاقي منتج اسمه {product_name}"

        product.price = new_price
        await db.flush()
        return f"تم تحديث سعر {product.name} إلى {new_price} جنيه ✅"

    elif action_type == "update_stock":
        product_name = action.get("product_name", "")
        stock = action.get("stock_status", "in_stock")
        if not product_name:
            return "محتاج اسم المنتج"

        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.name.ilike(f"%{product_name}%"),
            ).limit(1)
        )
        product = result.scalar_one_or_none()
        if not product:
            return f"مش لاقي منتج اسمه {product_name}"

        if not product.attributes:
            product.attributes = {}
        product.attributes["stock_status"] = stock
        await db.flush()
        stock_ar = {"in_stock": "متوفر", "out_of_stock": "نفذ", "limited": "محدود"}.get(stock, stock)
        return f"تم تحديث حالة {product.name} إلى {stock_ar} ✅"

    elif action_type == "add_product":
        name = action.get("name", "")
        price = action.get("price", 0)
        if not name:
            return "محتاج اسم المنتج"

        product = Product(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=name,
            price=price,
            is_active=True,
            source="owner",
        )
        if action.get("description"):
            product.attributes = {"description": action["description"]}
        db.add(product)
        await db.flush()
        return f"تم إضافة المنتج {name} بسعر {price} جنيه ✅"

    elif action_type == "delete_product":
        product_name = action.get("product_name", "")
        if not product_name:
            return "محتاج اسم المنتج"

        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.name.ilike(f"%{product_name}%"),
            ).limit(1)
        )
        product = result.scalar_one_or_none()
        if not product:
            return f"مش لاقي منتج اسمه {product_name}"

        product.is_active = False
        await db.flush()
        return f"تم حذف {product.name} ✅"

    elif action_type == "update_shipping":
        if action.get("inside_cairo"):
            tenant.delivery_inside_cairo = action["inside_cairo"]
        if action.get("outside_cairo"):
            tenant.delivery_outside_cairo = action["outside_cairo"]
        if action.get("free_above"):
            tenant.free_delivery_above = action["free_above"]
        await db.flush()
        return f"تم تحديث الشحن: القاهرة {tenant.delivery_inside_cairo}ج، باقي المحافظات {tenant.delivery_outside_cairo}ج ✅"

    elif action_type == "info_request":
        return "تمام، بسألك... (محتاج توضيح)"

    else:
        return "مش فاهم الأمر ده. جرب قول like: 'حدّث سعر المنتج X لـ 123 جنيه'"
