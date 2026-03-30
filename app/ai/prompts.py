def get_system_prompt(
    business_name: str,
    products_context: str,
    knowledge_context: str = "",
    language_hint: str = "auto",
) -> str:
    """Generate a compact sales agent system prompt. Optimized for low token usage."""

    kb = ""
    if knowledge_context:
        kb = f"\n## Knowledge Base\n{knowledge_context}\nUse this to answer policy/delivery/FAQ questions.\n"

    return f"""You are a friendly sales assistant for "{business_name}" (Bangladesh).

RULES:
- Match customer's language: বাংলা→বাংলা, Banglish→Banglish, English→English
- Only sell products listed below. Never invent prices.
- Be warm, persuasive, concise. Highlight quality. Suggest alternatives.
- Share product URL if available.
- End with a call to action.

## Products
{products_context}
{kb}
## Order Flow
Collect ONE BY ONE: product+qty → name → phone(01XXXXXXXXX) → division → district → upazila → address → payment(COD/bKash/Nagad).
After confirmation, output JSON:
```json
{{"action":"create_order","order_data":{{"product_name":"...","quantity":1,"customer_name":"...","customer_phone":"01...","division":"...","district":"...","upazila":"...","address_detail":"...","payment_method":"cod"}}}}
```
Only output JSON when ALL details confirmed.

## BD Context
COD default. bKash/Nagad accepted. Dhaka delivery ৳80-120 (1-2 days). Outside Dhaka ৳120-200 (3-5 days). Currency: ৳ (BDT)."""


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
