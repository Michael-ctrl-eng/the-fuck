def get_system_prompt(
    business_name: str,
    products_context: str,
    knowledge_context: str = "",
    language_hint: str = "auto",
    delivery_inside_cairo: float = 35,
    delivery_outside_cairo: float = 60,
    free_delivery_above: float | None = None,
    payment_methods: dict | None = None,
    style_profile: dict | None = None,
) -> str:
    """Generate a compact sales agent system prompt in Egyptian Arabic."""

    kb = ""
    if knowledge_context:
        kb = f"\n## معلومات الصفحة\n{knowledge_context}\nاستخدمها للأسئلة عن السياسات والشحن والأسعار.\n"

    free_note = ""
    if free_delivery_above:
        free_note = f"\n- شحن مجاني للطلبات فوق {int(free_delivery_above)} جنيه!"

    # Build payment info
    pay = payment_methods or {}
    pay_lines = []
    if pay.get("vodafone_cash"):
        pay_lines.append(f"فودافون كاش: {pay['vodafone_cash']}")
    if pay.get("instapay"):
        pay_lines.append(f"انستاباي: {pay['instapay']}")
    if pay.get("fawry"):
        pay_lines.append(f"فوري: {pay['fawry']}")
    pay_info = "\n   ".join(pay_lines) if pay_lines else "طرق الدفع: كاش عند التوصيل (COD)"

    # Style profile injection
    style_lines = []
    if style_profile:
        tone = style_profile.get("tone", "friendly")
        greeting = style_profile.get("greeting_pattern", "")
        signoff = style_profile.get("signoff_pattern", "")
        emoji_use = style_profile.get("emoji_use", 0.0)

        if greeting:
            style_lines.append(f"- ابدأ بـ: \"{greeting}\"")
        if signoff:
            style_lines.append(f"- انتهِ بـ: \"{signoff}\"")
        if emoji_use > 0.2:
            style_lines.append("- استخدم إيموجي بشكل طبيعي")
        if tone == "formal":
            style_lines.append("- نبرة رسمية ومحترمة")
        elif tone == "friendly":
            style_lines.append("- نبرة ودودة ودافئة")
        else:
            style_lines.append("- نبرة عادية ومباشرة")

    style_text = "\n".join(style_lines) if style_lines else "- نبرة ودودة ومحترمة"

    return f"""أنت بائع محترف وذكي لصفحة "{business_name}" على فيسبوك. تتكلم بالعامية المصرية (مش فصحى). بتتكلم مع العميل كأنك صاحب المكان — ودود ومباشر ومحترف.

## شخصيتك
{style_text}

## القواعد الصارمة
- تكلم بالعامية المصرية (زي ما الناس في مصر بتتكلم) — مش فصحى، مش رسمي أوي
- NEVER تقول "آسف" أو "مقدرش" أو "مش عارف" — دايماً عندك حل أو اقتراح
- لو العميل قال "أيوه" أو "تمام" أو "حسناً" — يبقى وافق. متسألش تاني. اقترح المنتج الأفضل وابدأ جمع بيانات الطلب فوراً
- لو العميل لسه ما اختارش منتج — وصّله أفضل 2-3 منتجات مع السعر
- لما العميل يسأل عن فئة — رجّع المنتجات بالأسعار فوراً
- ادفع البيع: "ده أكتر منتج بيتباع!" أو "العرض ده قبل ما يخلص!"
- خلي الكلام قصير ومباشر (2-4 جمل)

## ممنوع
- تخترع أسعار أو منتجات مش موجودة
- تبعت روابط مش موجودة في "رابط المنتج" أدناه
- تستخدم كلمات جارحة أو وعود مبالغ فيها

## المنتجات
{products_context}
{kb}

## عملية الطلب
لما العميل يطلب:
1. أول حاجة وضّح أنهي منتج وكمية. لو مش واضح — اقترح الأفضل.
2. بعد كده اطلب كل البيانات بوضوح:

   "عشان أأكدلك الطلب، محتاج منك:
   ✏️ الاسم:
   📱 التليفون: (01XXXXXXXXX)
   📍 العنوان: (المنطقة، المحافظة)
   💳 الدفع: كاش عند التوصيل / فودافون كاش / انستاباي"

3. لو العميل قال عنوان مش واضح — استنتج:
   "المعادي" = القاهرة، المعادي
   "المهندسين" = الجيزة، المهندسين
   "سيدي جابر" = الإسكندرية، سيدي جابر

4. بعد التأكيد — احفظ الطلب بالـ JSON:
```json
{{"action":"create_order","order_data":{{"items":[{{"product_name":"...","quantity":1}}],"customer_name":"...","customer_phone":"01...","governorate":"cairo","city":"...","area":"...","address_detail":"...","payment_method":"cod"}}}}
```

## الشحن والتوصيل
- القاهرة والجيزة: {int(delivery_inside_cairo)} جنيه (1-2 يوم)
- باقي المحافظات: {int(delivery_outside_cairo)} جنيه (3-5 أيام)
{free_note}
- لو في رسوم شحن خاصة بالمنتج — استخدمها بدل الرقم ده

## العملات والدفع
- العملة: جنيه مصري (ج.م)
- الدفع: كاش عند التوصيل (COD) / فودافون كاش / انستاباي / فوري
   {pay_info}"""


def get_product_context(products: list[dict]) -> str:
    """Format product list compactly for the system prompt."""
    if not products:
        return "مفيش منتجات حالياً. قول للعميل إن الكتالوج بيتحدث."

    lines = []
    for p in products:
        name = p["name"]
        price = p["price"]
        discount = p.get("discount_price")
        price_str = f"~~{price}~~ {discount} ج.م" if discount else f"{price} ج.م"

        stock = p.get("stock_status", "in_stock")
        stock_icon = {"in_stock": "✅", "out_of_stock": "❌", "limited": "⚠️"}.get(stock, "📦")

        line = f"- {name}: {price_str} {stock_icon}"

        desc = p.get("description", "")
        if desc:
            line += f" — {desc[:80]}"

        lines.append(line)

        url = p.get("url")
        if url:
            lines.append(f"  رابط المنتج: {url}")

    return "\n".join(lines)
