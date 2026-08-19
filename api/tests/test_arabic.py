from __future__ import annotations

from api.app.services.arabic import (
    detect_dialect,
    detect_intent,
    extract_entities,
    is_arabizi,
    moderation_check,
    normalize_arabic,
    quality_score,
    transliterate_arabizi,
)


def test_normalize_arabic_variants():
    # hamza unification + teh-marbuta unification (strong mode)
    assert normalize_arabic("أهلاً إلَى ٱلْعَرَبِيَّة") == "اهلا الى العربيه"
    assert normalize_arabic("مَرْحَبًا") == "مرحبا"
    assert normalize_arabic("السَّلامُ عَلَيْكُمْ") == "السلام عليكم"


def test_normalize_numerals_and_punctuation():
    assert normalize_arabic("سعر ١٢٣ جنيه و ٤٥٦") == "سعر 123 جنيه و 456"
    assert normalize_arabic("كم السعر؟؟") == "كم السعر?"
    assert normalize_arabic("هذا، وذاك؛ وأيضا") == "هذا, وذاك; وايضا"


def test_arabizi_detection_and_transliteration():
    assert is_arabizi("ana 3ayez as2al 3an el sa3r")
    assert not is_arabizi("أنا عايز أسأل عن السعر")
    text, conf = transliterate_arabizi("ana 3ayez as2al")
    assert "عايز" in text or "عي" in text
    assert conf > 0.5


def test_dialect_egyptian():
    res = detect_dialect("إيه يا معلم، عايز أعرف السعر كده بسرعة أوي")
    assert res["label"] in ("egyptian", "mixed")
    assert res["confidence"] > 0.3


def test_dialect_saudi():
    res = detect_dialect("وشلونكم؟ أبغى أطلب مندي، الحين توه فاتح المطعم")
    assert res["label"] in ("saudi", "gulf", "mixed")


def test_dialect_maghrebi():
    res = detect_dialect("واش رايك؟ دابا نجي نشري، واخا بزاف")
    assert res["label"] in ("maghrebi", "mixed")


def test_dialect_msa():
    res = detect_dialect("هل يمكنني معرفة سعر المنتج من فضلك؟ شكراً جزيلاً")
    assert res["label"] in ("msa", "mixed")


def test_dialect_unknown_short():
    res = detect_dialect("xyz")
    assert res["label"] in ("unknown", "arabizi")


def test_intent_detection():
    assert detect_intent("كم سعر الشنطة؟")["label"] == "question"
    assert detect_intent("أريد شراء الحذاء بكم سعره")["label"] in ("purchase", "question")
    assert detect_intent("المنتج وصلني مكسور والجودة سيئة جداً")["label"] == "complaint"
    assert detect_intent("اربح 500 جنيه يومياً اضغط على الرابط")["label"] == "spam"
    assert detect_intent("السلام عليكم كيف حالكم")["label"] in ("greeting", "question")


def test_moderation_critical_and_spam():
    res = moderation_check("أنت غبي وابن الكلب، سأشكو عليك")
    assert res["decision"] == "escalate"
    assert any(f["severity"] == "critical" for f in res["flags"])

    res = moderation_check("انضم الآن واربح من المنزل اضغط على الرابط")
    assert res["decision"] == "flag"

    res = moderation_check("شكراً على الخدمة الرائعة")
    assert res["decision"] == "skip"


def test_moderation_no_substring_false_positives():
    # «لص» must not match inside خالص / الصبح — whole-word matching only
    res = moderation_check("خلصت المهمة خالص، الصبح هجي المكتب")
    assert res["decision"] == "skip"
    assert res["flags"] == []

    res = moderation_check("شكرا على الخدمة، فين أقرب فرع؟")
    assert res["decision"] == "skip"


def test_moderation_inflected_forms_still_match():
    # light stemming: ال/وال prefixes and ين/ات/ة suffixes must still hit
    res = moderation_check("اللص والكذاب نصابين، الجودة حقيرة")
    assert any(f["severity"] == "critical" for f in res["flags"])
    assert any(f["matched"] == "نصاب" for f in res["flags"])
    assert any(f["matched"] == "كذاب" for f in res["flags"])


def test_moderation_privacy():
    res = moderation_check("تواصل معي على 01012345678 أو a@b.com")
    assert any(f["severity"] == "privacy" for f in res["flags"])


def test_entities():
    ents = extract_entities("اتصل بنا على 01012345678 أو sales@shop.com و زوروا #عروض اليوم")
    assert ents["phones"]
    assert ents["emails"] == ["sales@shop.com"]
    assert ents["hashtags"] == ["#عروض"]


def test_entities_prices():
    ents = extract_entities("السعر 850 جنيه أو 120 ريال للقطعة")
    assert len(ents["prices"]) == 2


def test_quality_score():
    good = quality_score("السلام عليكم، أريد الاستفسار عن مواعيد العمل وشكراً جزيلاً لكم")
    assert good["score"] > 0.6
    bad = quality_score("؟")
    assert bad["score"] < 0.5
