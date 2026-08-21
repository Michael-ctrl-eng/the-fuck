"""Egyptian address hierarchy — 27 Governorates with cities/areas."""

# Egyptian governorates with their zones and typical shipping costs
GOVERNORATES = {
    "cairo": {
        "name_ar": "القاهرة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المعادي", "مصر الجديدة", "مدينة نصر", "شبرا", "العبور", "حلوان",
            "الزمالك", "وسط البلد", "المنيل", "دار السلام", "البساتين",
            "المقطم", "التجمع الخامس", "التجمع الثالث", "الشروق", "البدر",
            "نادي الشمس", "ماونتن فيو", "العليا", "الFinance District",
        ],
    },
    "giza": {
        "name_ar": "الجيزة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المهندسين", "الدقي", "الهرم", "فيصل", "أكتوبر", "المحور",
            "العجوزة", "المنيل", "الزمالك", "ال觯.swt", "الوراق",
            "البدرشين", "أوسيم", "كرداسة", "ال OA.",
        ],
    },
    "alexandria": {
        "name_ar": "الإسكندرية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": [
            "سيدي جابر", "سموحة", "المنشية", "الrichter", "الجمرك",
            "ال传奇", "ال.askar", "الرمل", "اللبان", "جليم", "العجمي",
            "الأ/deux", "كفر عبده", "المكس", "ال的故事",
        ],
    },
    "qalyubia": {"name_ar": "القليوبية", "zone": 2, "shipping_cost": 45, "free_threshold": 500},
    "sharqia": {"name_ar": "الشرقية", "zone": 2, "shipping_cost": 50, "free_threshold": 500},
    "gharbia": {"name_ar": "الغربية", "zone": 2, "shipping_cost": 50, "free_threshold": 500},
    "monufia": {"name_ar": "المنوفية", "zone": 2, "shipping_cost": 50, "free_threshold": 500},
    "beheira": {"name_ar": "البحيرة", "zone": 3, "shipping_cost": 60, "free_threshold": 600},
    "kafr-el-sheikh": {"name_ar": "كفر الشيخ", "zone": 3, "shipping_cost": 60, "free_threshold": 600},
    "damietta": {"name_ar": "دمياط", "zone": 3, "shipping_cost": 60, "free_threshold": 600},
    "port-said": {"name_ar": "بورسعيد", "zone": 3, "shipping_cost": 60, "free_threshold": 600},
    "ismailia": {"name_ar": "الإسماعيلية", "zone": 3, "shipping_cost": 55, "free_threshold": 600},
    "suez": {"name_ar": "السويس", "zone": 3, "shipping_cost": 55, "free_threshold": 600},
    "beni-suef": {"name_ar": "بني سويف", "zone": 3, "shipping_cost": 65, "free_threshold": 700},
    "fayoum": {"name_ar": "الفيوم", "zone": 3, "shipping_cost": 65, "free_threshold": 700},
    "minya": {"name_ar": "المنيا", "zone": 4, "shipping_cost": 75, "free_threshold": 800},
    "assiut": {"name_ar": "أسيوط", "zone": 4, "shipping_cost": 75, "free_threshold": 800},
    "sohag": {"name_ar": "سوهاج", "zone": 4, "shipping_cost": 80, "free_threshold": 800},
    "qena": {"name_ar": "قنا", "zone": 4, "shipping_cost": 80, "free_threshold": 800},
    "luxor": {"name_ar": "الأقصر", "zone": 4, "shipping_cost": 85, "free_threshold": 800},
    "aswan": {"name_ar": "أسوان", "zone": 4, "shipping_cost": 85, "free_threshold": 800},
    "red-sea": {"name_ar": "البحر الأحمر", "zone": 4, "shipping_cost": 90, "free_threshold": 900},
    "new-valley": {"name_ar": "الوادي الجديد", "zone": 5, "shipping_cost": 100, "free_threshold": 1000},
    "matrouh": {"name_ar": "مطروح", "zone": 5, "shipping_cost": 100, "free_threshold": 1000},
    "north-sinai": {"name_ar": "شمال سيناء", "zone": 5, "shipping_cost": 100, "free_threshold": 1000},
    "south-sinai": {"name_ar": "جنوب سيناء", "zone": 4, "shipping_cost": 90, "free_threshold": 900},
}

# Egyptian phone number validation
EGYPTIAN_PHONE_REGEX = r"^(?:\+20|0020|0)?(1[0125]\d{8})$"


def validate_egyptian_phone(phone: str) -> bool:
    """Validate Egyptian phone number format."""
    import re
    return bool(re.match(EGYPTIAN_PHONE_REGEX, phone.replace(" ", "").replace("-", "")))


def detect_governorate_from_text(text: str) -> str | None:
    """Detect Egyptian governorate from free text."""
    if not text:
        return None
    normalized = text.lower().strip()
    for key, info in GOVERNORATES.items():
        if info["name_ar"] in normalized or key in normalized:
            return key
    return None


def calculate_shipping(
    governorate: str,
    cart_total: float = 0.0,
    default_inside: float = 35,
    default_outside: float = 60,
) -> dict:
    """Calculate shipping cost for an Egyptian governorate."""
    info = GOVERNORATES.get(governorate)
    if not info:
        return {
            "cost": default_outside,
            "free": False,
            "governorate": governorate,
            "message": f"شحن {default_outside} جنيه",
        }

    cost = info["shipping_cost"]
    threshold = info["free_threshold"]
    is_free = cart_total >= threshold

    if is_free:
        return {
            "cost": 0,
            "free": True,
            "governorate": governorate,
            "governorate_ar": info["name_ar"],
            "message": f"شحن مجاني! (للطلبات فوق {threshold} جنيه)",
        }

    return {
        "cost": cost,
        "free": False,
        "governorate": governorate,
        "governorate_ar": info["name_ar"],
        "message": f"شحن {cost} جنيه إلى {info['name_ar']}",
        "free_threshold": threshold,
        "remaining": threshold - cart_total,
    }
