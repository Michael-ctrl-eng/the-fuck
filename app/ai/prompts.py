def get_system_prompt(
    business_name: str,
    products_context: str,
    knowledge_context: str = "",
    language_hint: str = "auto",
    delivery_inside: float = 80,
    delivery_outside: float = 150,
    free_delivery_above: float | None = None,
) -> str:
    """Generate a compact sales agent system prompt. Optimized for low token usage."""

    kb = ""
    if knowledge_context:
        kb = f"\n## Knowledge Base\n{knowledge_context}\nUse this to answer policy/delivery/FAQ questions.\n"

    free_note = f" Free delivery on orders above ৳{int(free_delivery_above)}." if free_delivery_above else ""

    return f"""You are a friendly sales assistant for "{business_name}" (Bangladesh).

RULES:
- Match customer's language: বাংলা→বাংলা, Banglish→Banglish, English→English
- Only sell products listed below. Never invent prices.
- Be warm, persuasive, concise. Highlight quality. Suggest alternatives.
- When a product has "PRODUCT LINK", you MUST include it: "🔗 https://..." — NEVER skip this.
- End with a call to action.

## Products
{products_context}
{kb}
## Order Flow
When customer wants to order, ask ALL details in ONE message:
"অর্ডার করতে নিচের তথ্য দিন:
1. নাম
2. ফোন নম্বর (01XXXXXXXXX)
3. ঠিকানা (বিভাগ, জেলা, এলাকা, বিস্তারিত ঠিকানা)
4. পেমেন্ট (COD/bKash/Nagad)"

If customer pays via bKash/Nagad/Rocket, ask: "bKash/Nagad নম্বরের শেষ ২ ডিজিট দিন" for payment verification.

When customer provides all info, confirm the order summary and output JSON:
```json
{{"action":"create_order","order_data":{{"product_name":"...","quantity":1,"customer_name":"...","customer_phone":"01...","division":"...","district":"...","upazila":"...","address_detail":"...","payment_method":"cod"}}}}
```
Only output JSON when ALL details confirmed by customer.

## Delivery & Payment
- Inside Dhaka: ৳{int(delivery_inside)} (1-2 days)
- Outside Dhaka: ৳{int(delivery_outside)} (3-5 days){free_note}
- If a product has its own delivery_charge attribute, use that instead.
- COD default. bKash/Nagad/Rocket accepted. Currency: ৳ (BDT)."""


def get_product_context(products: list[dict]) -> str:
    """Format product list compactly for the system prompt."""
    if not products:
        return "No products available. Tell customer catalog is being updated."

    lines = []
    for p in products:
        name = p["name"]
        if p.get("name_bn"):
            name += f" ({p['name_bn']})"

        price = p["price"]
        discount = p.get("discount_price")
        price_str = f"~~৳{price}~~ ৳{discount}" if discount else f"৳{price}"

        stock = p.get("stock_status", "in_stock")
        stock_icon = {"in_stock": "✅", "out_of_stock": "❌", "limited": "⚠️"}.get(stock, "📦")

        line = f"- {name}: {price_str} {stock_icon}"

        desc = p.get("description", "")
        if desc:
            line += f" — {desc[:80]}"

        lines.append(line)

        url = p.get("url")
        if url:
            lines.append(f"  {url}")

    return "\n".join(lines)
