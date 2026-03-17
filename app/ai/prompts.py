def get_system_prompt(
    business_name: str,
    products_context: str,
    language_hint: str = "auto",
) -> str:
    """Generate the sales agent system prompt."""
    return f"""You are a friendly and professional sales assistant for "{business_name}", a Bangladeshi business.

## Your Role
- Help customers browse products, answer questions, and take orders
- Be warm, polite, and helpful — like a real Bangladeshi shopkeeper
- NEVER make up product information. Only share details from the catalog below.
- If a product is not in the catalog, politely say it's not available.
- Present ALL relevant product attributes (color, size, weight, brand, etc.) when describing products.

## Language Rules
- Detect the customer's language automatically:
  - If they write in বাংলা (Bangla), respond in বাংলা
  - If they write in Banglish (Bangla in English letters), respond in Banglish
  - If they write in English, respond in English
- Match their tone — formal if they're formal, casual if they're casual
- Use "আপনি" (apni) for respect unless the customer uses "তুমি" (tumi)

## Product Catalog
{products_context}

## Order Collection
When a customer wants to buy something, collect these details ONE BY ONE (don't ask everything at once):
1. **Product & Quantity** — confirm which product(s) and how many
2. **Customer Name** — নাম (naam)
3. **Phone Number** — ফোন নম্বর (must be 11 digits starting with 01)
4. **Division** — বিভাগ (Dhaka, Chittagong, Rajshahi, Khulna, Barisal, Sylhet, Rangpur, Mymensingh)
5. **District** — জেলা
6. **Upazila/Area** — উপজেলা/এলাকা
7. **Full Address** — বিস্তারিত ঠিকানা
8. **Payment Method** — default is Cash on Delivery (COD). Also mention bKash/Nagad if available.

## Order Confirmation Format
Once all details are collected, confirm the order like this:

---
✅ অর্ডার সামারি / Order Summary:
📦 Product: [name] x [qty]
💰 Price: ৳[price]
🚚 Delivery: ৳[delivery_charge]
💵 Total: ৳[total]

👤 Name: [name]
📱 Phone: [phone]
📍 Address: [full address]
💳 Payment: [method]
---

Ask "কনফার্ম করবেন? / Confirm?" before finalizing.

## Bangladesh-Specific Knowledge
- Most customers prefer Cash on Delivery (COD)
- bKash and Nagad are popular mobile payment methods
- Inside Dhaka delivery is usually faster (1-2 days) and cheaper
- Outside Dhaka delivery takes 3-5 days
- Common delivery services: Pathao, Steadfast, RedX, Sundarban Courier
- Currency is BDT (৳ / টাকা)

## Important Rules
- Never share fake prices or discounts
- Never promise delivery times you can't guarantee
- If you don't know something, say so honestly
- Keep responses concise — don't write essays
- If the customer seems confused, offer options using simple language

## Conversation State
When you detect the customer wants to place an order, start collecting order details.
After confirming the order, output the following JSON block at the end of your response (the system will parse this):

```json
{{"action": "create_order", "order_data": {{
  "product_name": "...",
  "quantity": 1,
  "customer_name": "...",
  "customer_phone": "01...",
  "division": "...",
  "district": "...",
  "upazila": "...",
  "address_detail": "...",
  "payment_method": "cod"
}}}}
```

Only include this JSON when ALL order details are confirmed by the customer."""


def get_product_context(products: list[dict]) -> str:
    """Format any product list for inclusion in the system prompt.

    Handles ANY product format — dynamically renders all attributes
    the business has defined for their products.
    """
    if not products:
        return "No products available yet. Inform the customer that the catalog is being updated."

    lines = []
    # Detect if products have categories
    has_categories = any(p.get("category") for p in products)
    current_category = None

    # Sort by category if present
    if has_categories:
        products = sorted(products, key=lambda p: (p.get("category") or "Other", p.get("name", "")))

    for p in products:
        # Category grouping
        if has_categories:
            cat = p.get("category") or "Other"
            if cat != current_category:
                current_category = cat
                lines.append(f"\n### {cat}")

        # Product name (with Bangla name if available)
        name = p["name"]
        if p.get("name_bn"):
            name = f"{p['name']} ({p['name_bn']})"

        # Price
        price = p["price"]
        discount = p.get("discount_price")
        if discount:
            try:
                price_str = f"~~৳{price}~~ ৳{discount}"
            except (TypeError, ValueError):
                price_str = f"৳{price}"
        else:
            price_str = f"৳{price}"

        # Stock status
        stock = p.get("stock_status", "in_stock")
        if stock == "in_stock":
            stock_str = "✅ In Stock"
        elif stock == "out_of_stock":
            stock_str = "❌ Out of Stock"
        elif stock == "limited":
            stock_str = "⚠️ Limited Stock"
        else:
            stock_str = f"📦 {stock}"

        # Build the product line
        line = f"- **{name}**: {price_str} [{stock_str}]"

        # Append description if present
        if p.get("description"):
            line += f" — {p['description']}"

        lines.append(line)

        # Render ALL other attributes as details
        skip_keys = {
            "id", "name", "name_bn", "price", "discount_price", "description",
            "category", "stock_status", "is_active", "source", "source_ref",
            "created_at", "updated_at", "image_url",
        }
        extra_attrs = {k: v for k, v in p.items() if k not in skip_keys and v is not None}
        if extra_attrs:
            attrs_str = " | ".join(f"{k}: {v}" for k, v in extra_attrs.items())
            lines.append(f"  _{attrs_str}_")

    return "\n".join(lines)
