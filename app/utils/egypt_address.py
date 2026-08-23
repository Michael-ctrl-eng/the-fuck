"""Egyptian address hierarchy — 27 Governorates with areas + shipping zones."""

# Zone 1 = Cairo & Giza (inside), zones 2+ = outside. Costs in EGP.
GOVERNORATES = {
    "cairo": {
        "name_ar": "القاهرة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المعادي", "مصر الجديدة", "مدينة نصر", "شبرا", "العبور", "حلوان",
            "الزمالك", "وسط البلد", "المنيل", "دار السلام", "البساتين",
            "المقطم", "التجمع الخامس", "التجمع الثالث", "الشروق", "الرحاب",
            "مدينتي", "نادي الشمس", "العتبة", "باب اللوق", "الظاهر",
            "عين شمس", "المرج", "السلام", "النزهة",
        ],
    },
    "giza": {
        "name_ar": "الجيزة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المهندسين", "الدقي", "الهرم", "فيصل", "6 أكتوبر", "الشيخ زايد",
            "العجوزة", "إمبابة", "بولاق الدكرور", "الوراق", "أوسيم",
            "كرداسة", "البدرشين", "الصف", "أطفيح", "الواحات البحرية",
        ],
    },
    "alexandria": {
        "name_ar": "الإسكندرية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": [
            "سيدي جابر", "سموحة", "المنشية", "الجمرك", "الرمل", "جليم",
            "العجمي", "كفر عبده", "المكس", "محرم بك", "الإبراهيمية",
            "العصافرة", "سيدي بشر", "المندرة", "برج العرب", "المعمورة",
        ],
    },
    "qalyubia": {
        "name_ar": "القليوبية", "zone": 2, "shipping_cost": 45, "free_threshold": 500,
        "areas": ["بنها", "شبرا الخيمة", "القليوبية", "قها", "الخانكة", "طوخ", "العبور"],
    },
    "sharqia": {
        "name_ar": "الشرقية", "zone": 2, "shipping_cost": 50, "free_threshold": 500,
        "areas": ["الزقازيق", "العاشر من رمضان", "بلبيس", "منيا القمح", "أبو حماد", "فاقوس"],
    },
    "dakahlia": {
        "name_ar": "الدقهلية", "zone": 2, "shipping_cost": 50, "free_threshold": 500,
        "areas": ["المنصورة", "ميت غمر", "طلخا", "دكرنس", "بلقاس", "أجا", "المنزلة", "ميت سلسيل"],
    },
    "gharbia": {
        "name_ar": "الغربية", "zone": 2, "shipping_cost": 50, "free_threshold": 500,
        "areas": ["طنطا", "المحلة الكبرى", "كفر الزيات", "زفتى", "السنطة", "قطور", "بسيون"],
    },
    "monufia": {
        "name_ar": "المنوفية", "zone": 2, "shipping_cost": 50, "free_threshold": 500,
        "areas": ["شبين الكوم", "منوف", "سرس الليان", "أشمون", "قويسنا", "الشهداء", "بركة السبع"],
    },
    "beheira": {
        "name_ar": "البحيرة", "zone": 3, "shipping_cost": 60, "free_threshold": 600,
        "areas": ["دمنهور", "كفر الدوار", "رشيد", "إدفينا", "حوش عيسى", "أبو المطامير", "وادي النطرون"],
    },
    "kafr-el-sheikh": {
        "name_ar": "كفر الشيخ", "zone": 3, "shipping_cost": 60, "free_threshold": 600,
        "areas": ["كفر الشيخ", "دسوق", "بلطيم", "مطوبس", "الحامول", "بيلا"],
    },
    "damietta": {
        "name_ar": "دمياط", "zone": 3, "shipping_cost": 60, "free_threshold": 600,
        "areas": ["دمياط", "رأس البر", "فارسكور", "كفر سعد", "الزرقا"],
    },
    "port-said": {
        "name_ar": "بورسعيد", "zone": 3, "shipping_cost": 60, "free_threshold": 600,
        "areas": ["بورفؤاد", "المناخ", "الضواحي", "الزهور", "العرب", "حي الشرق"],
    },
    "ismailia": {
        "name_ar": "الإسماعيلية", "zone": 3, "shipping_cost": 55, "free_threshold": 600,
        "areas": ["الإسماعيلية", "فايد", "القنطرة", "التل الكبير", "أبو صوير", "القصاصين الجديدة"],
    },
    "suez": {
        "name_ar": "السويس", "zone": 3, "shipping_cost": 55, "free_threshold": 600,
        "areas": ["الأربعين", "السويس", "عتاقة", "الجناين", "فيصل"],
    },
    "beni-suef": {
        "name_ar": "بني سويف", "zone": 3, "shipping_cost": 65, "free_threshold": 700,
        "areas": ["بني سويف", "الواسطى", "ناصر", "إهناسيا", "ببا", "الفشن"],
    },
    "fayoum": {
        "name_ar": "الفيوم", "zone": 3, "shipping_cost": 65, "free_threshold": 700,
        "areas": ["الفيوم", "الفيوم الجديدة", "طامية", "سنورس", "إطسا", "إبشواي", "يوسف الصديق"],
    },
    "minya": {
        "name_ar": "المنيا", "zone": 4, "shipping_cost": 75, "free_threshold": 800,
        "areas": ["المنيا", "ملوي", "بني مزار", "مغاغة", "سمالوط", "مطاي", "دير مواس", "العدوة"],
    },
    "assiut": {
        "name_ar": "أسيوط", "zone": 4, "shipping_cost": 75, "free_threshold": 800,
        "areas": ["أسيوط", "ديروط", "منفلوط", "القوصية", "أبنوب", "الغنايم", "ساحل سليم", "البداري"],
    },
    "sohag": {
        "name_ar": "سوهاج", "zone": 4, "shipping_cost": 80, "free_threshold": 800,
        "areas": ["سوهاج", "أخميم", "البلينا", "المراغة", "طهطا", "المنشاة", "دار السلام", "جهينة"],
    },
    "qena": {
        "name_ar": "قنا", "zone": 4, "shipping_cost": 80, "free_threshold": 800,
        "areas": ["قنا", "نجع حمادي", "قفط", "نجع حمادي", "دشنا", "الأقصر القديمة", "فرشوط", "وقفة"],
    },
    "luxor": {
        "name_ar": "الأقصر", "zone": 4, "shipping_cost": 85, "free_threshold": 800,
        "areas": ["الأقصر", "إسنا", "أرمنت", "القرنة", "الطود", "البياضية"],
    },
    "aswan": {
        "name_ar": "أسوان", "zone": 4, "shipping_cost": 85, "free_threshold": 800,
        "areas": ["أسوان", "كوم أمبو", "إدفو", "دراو", "السباعية", "نصر النوبة", "كلابشة"],
    },
    "red-sea": {
        "name_ar": "البحر الأحمر", "zone": 4, "shipping_cost": 90, "free_threshold": 900,
        "areas": ["الغردقة", "سفاجا", "مرسى علم", "القصير", "رأس غارب"],
    },
    "new-valley": {
        "name_ar": "الوادي الجديد", "zone": 5, "shipping_cost": 100, "free_threshold": 1000,
        "areas": ["الخارجة", "الداخلة", "الفرافرة", "باريس", "بلاط"],
    },
    "matrouh": {
        "name_ar": "مطروح", "zone": 5, "shipping_cost": 100, "free_threshold": 1000,
        "areas": ["مرسى مطروح", "العلامين", "الساحل الشمالي", "النجيلة", "سيدي براني", "السلوم"],
    },
    "north-sinai": {
        "name_ar": "شمال سيناء", "zone": 5, "shipping_cost": 100, "free_threshold": 1000,
        "areas": ["العريش", "بئر العبد", "الشيخ زويد", "رفح", "الحسنة"],
    },
    "south-sinai": {
        "name_ar": "جنوب سيناء", "zone": 4, "shipping_cost": 90, "free_threshold": 900,
        "areas": ["شرم الشيخ", "دهب", "Nuweiba", "طور سيناء", "سانت كاترين", "أبو رديس"],
    },
}

assert len(GOVERNORATES) == 27, f"Expected 27 governorates, got {len(GOVERNORATES)}"

EGYPTIAN_PHONE_REGEX = r"^(?:\+20|0020|0)?(1[0125]\d{8})$"


def validate_egyptian_phone(phone: str) -> bool:
    """Validate Egyptian phone number format."""
    import re

    return bool(re.match(EGYPTIAN_PHONE_REGEX, re.sub(r"[\s\-()]", "", phone or "")))


def get_governorates() -> list[str]:
    """List all governorate keys (27)."""
    return list(GOVERNORATES.keys())


def get_cities(governorate: str) -> list[str]:
    """Main city label(s) for a governorate — its Arabic name plus key areas head."""
    info = GOVERNORATES.get(governorate)
    if not info:
        return []
    return [info["name_ar"]]


def get_areas_for_governorate(governorate: str) -> list[str]:
    """All known areas/neighborhoods for a governorate."""
    info = GOVERNORATES.get(governorate)
    return list(info.get("areas", [])) if info else []


def validate_egyptian_address(governorate: str, city: str | None = None) -> bool:
    """Validate governorate (and optionally an area within it)."""
    info = GOVERNORATES.get((governorate or "").strip().lower())
    if not info:
        return False
    if not city:
        return True
    c = city.strip()
    if c == info["name_ar"]:
        return True
    return any(c == a.strip() for a in info.get("areas", []))


def find_governorate_for_city(city: str) -> str | None:
    """Reverse lookup: which governorate does this area/city belong to?"""
    needle = (city or "").strip()
    if not needle:
        return None
    for key, info in GOVERNORATES.items():
        if needle == info["name_ar"] or any(
            needle == a.strip() for a in info.get("areas", [])
        ):
            return key
    return None


def detect_governorate_from_text(text: str) -> str | None:
    """Detect Egyptian governorate from free text (Arabic name or key)."""
    if not text:
        return None
    normalized = text.lower().strip()
    # Prefer specific area hits over bare names
    for key, info in GOVERNORATES.items():
        for area in info.get("areas", []):
            a = area.strip()
            if len(a) > 2 and a in text:
                return key
    for key, info in GOVERNORATES.items():
        if info["name_ar"] in normalized or key.replace("-", " ") in normalized:
            return key
    return None


def calculate_shipping(
    governorate: str,
    cart_total: float = 0.0,
    default_inside: float = 35,
    default_outside: float = 60,
) -> dict:
    """Calculate shipping for an Egyptian governorate.

    Returns a dict: {cost, free, governorate, governorator_ar?, message, ...}
    Unknown governorates fall back to the outside-Cairo default.
    """
    info = GOVERNORATES.get((governorate or "").strip().lower())
    if not info:
        return {
            "cost": default_outside,
            "free": False,
            "governorate": governorate,
            "message": f"شحن {default_outside} جنيه",
        }

    cost = float(info["shipping_cost"])
    threshold = float(info["free_threshold"])

    if cart_total >= threshold:
        return {
            "cost": 0,
            "free": True,
            "governorate": governorate,
            "governorate_ar": info["name_ar"],
            "message": f"شحن مجاني! (للطلبات فوق {int(threshold)} جنيه)",
        }

    return {
        "cost": cost,
        "free": False,
        "governorate": governorate,
        "governorate_ar": info["name_ar"],
        "message": f"شحن {int(cost)} جنيه إلى {info['name_ar']}",
        "free_threshold": int(threshold),
        "remaining": round(threshold - cart_total, 2),
    }
