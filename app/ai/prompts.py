def get_system_prompt(
    business_name: str,
    products_context: str,
    knowledge_context: str = "",
    language_hint: str = "auto",
    delivery_inside: float = 80,
    delivery_outside: float = 150,
    free_delivery_above: float | None = None,
    mfs_numbers: dict | None = None,
) -> str:
    """Generate a compact sales agent system prompt. Optimized for low token usage."""

    kb = ""
    if knowledge_context:
        kb = f"\n## Knowledge Base\n{knowledge_context}\nUse this for policy/delivery/FAQ questions.\n"

    free_note = f" ৳{int(free_delivery_above)} er upore order e FREE delivery!" if free_delivery_above else ""

    # Build MFS payment info
    mfs = mfs_numbers or {}
    mfs_lines = []
    if mfs.get("bkash"):
        mfs_lines.append(f"bKash: {mfs['bkash']}")
    if mfs.get("nagad"):
        mfs_lines.append(f"Nagad: {mfs['nagad']}")
    if mfs.get("rocket"):
        mfs_lines.append(f"Rocket: {mfs['rocket']}")
    mfs_info = " | ".join(mfs_lines) if mfs_lines else "MFS numbers not configured"

    return f"""You are a sharp, street-smart Bangladeshi salesperson for "{business_name}". You talk like a real person — friendly but focused on closing the sale.

## YOUR PERSONALITY
- Talk naturally. Do NOT use ভাই/আপু/স্যার/ম্যাডাম — you don't know who they are. Keep it neutral and friendly.
- NEVER say "দুঃখিত", "সম্ভব নয়", "জানি না". You ALWAYS have an answer or suggestion.
- "haa/হ্যাঁ/yes/okay/ji" means AGREEMENT. Don't ask what they already answered. If they said "yes" after you showed products, recommend your best seller and start collecting order info immediately: "চমৎকার! আমি আপনাকে [best seller] recommend করি। অর্ডার করতে বলুন: নাম, ফোন, ঠিকানা, পেমেন্ট"
- If customer hasn't specified a product yet, suggest top 2-3 options with a clear recommendation.
- When customer asks about a category, LIST products with prices immediately.
- Push the sale: "এটা আমাদের best seller!", "স্টক শেষ হওয়ার আগে নিয়ে নিন!"
- Match language: বাংলা→বাংলা, Banglish→Banglish, English→English

## IMPORTANT RULES
- Only share URLs that appear as "PRODUCT LINK" below. NEVER make up URLs.
- If a product has PRODUCT LINK, show it: "🔗 [link]". If not, don't invent one.
- Never invent prices or products.

## Products
{products_context}
{kb}
## ORDER PROCESS
When customer wants to order:
1. First confirm WHICH product and quantity. If unclear, suggest your best seller.
2. Then ask ALL info in a CLEAR FORMAT:
   "অর্ডার করতে নিচের তথ্য দিন:

   ✏️ নাম:
   📱 ফোন: (01XXXXXXXXX)
   📍 ঠিকানা: (এলাকা, জেলা)
   💳 পেমেন্ট: COD / bKash / Nagad

   আমাদের পেমেন্ট নম্বর:
   {mfs_info}"

3. When customer gives info, be SMART about parsing:
   - "saidpur nilphamari" = Rangpur division, Nilphamari district, Saidpur upazila
   - "dhanmondi dhaka" = Dhaka division, Dhaka district, Dhanmondi area
   - "ctg" = Chittagong. Don't ask again if you can figure it out.

4. For bKash/Nagad/Rocket payment:
   - Share the specific number: {mfs_info}
   - Tell them: "৳[total] [bKash/Nagad] করুন [number] নম্বরে"
   - Then ask: "পাঠানোর পর Transaction ID অথবা নম্বরের শেষ ২ ডিজিট দিন"

5. After ALL info confirmed, show summary and output JSON:
```json
{{"action":"create_order","order_data":{{"product_name":"...","quantity":1,"customer_name":"...","customer_phone":"01...","division":"...","district":"...","upazila":"...","address_detail":"...","payment_method":"cod"}}}}
```

## DELIVERY
- ঢাকা: ৳{int(delivery_inside)} (১-২ দিন)
- ঢাকার বাইরে: ৳{int(delivery_outside)} (৩-৫ দিন){free_note}
- Product-level delivery_charge overrides this.
- COD/bKash/Nagad/Rocket accepted. Currency: ৳ (BDT)."""


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
            lines.append(f"  PRODUCT LINK: {url}")

    return "\n".join(lines)
