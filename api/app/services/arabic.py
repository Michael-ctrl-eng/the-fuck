"""Arabic language processing — first-party, deterministic, always available.

Layers:
1. Unicode normalization (variants, diacritics, tatweel, numerals, punctuation)
2. Arabizi → Arabic transliteration (best-effort with confidence)
3. Lexical dialect detection (EG/SA/Gulf/Lev/Iraqi/Maghrebi/MSA/arabizi/mixed/unknown)
4. Intent classification (question/support/purchase/complaint/praise/spam/greeting)
5. Moderation flags with severity (critical/warn/spam/privacy)
6. Entity extraction (emails, phones, URLs, mentions, hashtags, prices, numbers)
7. Quality scoring (language confidence, informativeness, length)

camel-tools is an optional enrichment hook (see _camel_features); the
lexical engine is fully functional without it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

_DIACRITICS = {
    "\u064b", "\u064c", "\u064d", "\u064e", "\u064f", "\u0650", "\u0651",
    "\u0652", "\u0653", "\u0654", "\u0655", "\u0656", "\u0657", "\u0658",
    "\u0659", "\u065a", "\u065b", "\u065c", "\u065d", "\u065e", "\u065f",
    "\u0670", "\u0640",
}
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}

_TRANSLIT = [
    ("sh", "ش"), ("kh", "خ"), ("th", "ث"), ("dh", "ذ"), ("gh", "غ"),
    ("zh", "ژ"), ("ch", "تش"), ("ee", "ي"), ("oo", "و"), ("ah", "ة"),
    ("ei", "ي"), ("ou", "و"), ("a'", "ء"), ("2", "ء"), ("7", "ح"),
    ("9", "ق"), ("5", "خ"), ("6", "ط"), ("3", "ع"), ("4", "ذ"),
    ("8", "غ"), ("'", "ء"), ("ai", "اي"), ("ay", "اي"), ("ey", "اي"),
    ("ez", "ز"),
]
_LATIN_MAP = {
    "a": "ا", "b": "ب", "t": "ت", "j": "ج", "h": "ه", "d": "د", "r": "ر",
    "z": "ز", "s": "س", "f": "ف", "k": "ك", "l": "ل", "m": "م", "n": "ن",
    "w": "و", "y": "ي", "g": "ج", "p": "ب", "v": "ف", "q": "ق", "x": "كس",
    "i": "ي", "e": "ي", "o": "و", "u": "و", "c": "ك", "S": "ص", "D": "ض",
    "T": "ط", "Z": "ظ", "H": "ح", "K": "خ", "G": "غ", "E": "ع", "A": "ا",
}


def remove_diacritics(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if ch not in _DIACRITICS)


def remove_tatweel(text: str) -> str:
    return text.replace("\u0640", "")


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def unify_hamza(text: str) -> str:
    return (
        text.replace("\u0623", "\u0627")   # أ → ا
        .replace("\u0625", "\u0627")       # إ → ا
        .replace("\u0622", "\u0627")       # آ → ا
        .replace("\u0671", "\u0627")       # ٱ → ا
        .replace("\u0624", "\u0648")       # ؤ → و
        .replace("\u0626", "\u064a")       # ئ → ي
        .replace("\u06c0", "\u0647")       # ۀ → ه
    )


def unify_teh_marbuta(text: str) -> str:
    return text.replace("\u0629", "\u0647")  # ة → ه


def normalize_numerals(text: str) -> str:
    trans = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789",
    )
    return text.translate(trans)


def normalize_punctuation(text: str) -> str:
    trans = str.maketrans(
        {"،": ",", "؛": ";", "؟": "?", "٪": "%", "«": '"', "»": '"',
         "”": '"', "“": '"', "’": "'", "‘": "'", "٫": ".", "٬": ","}
    )
    text = text.translate(trans)
    text = re.sub(r"[!]{2,}", "!", text)
    text = re.sub(r"[?]{2,}", "?", text)
    return text


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_arabic(text: str, *, strong: bool = True) -> str:
    """Normalize Arabic text for storage/analysis.

    strong=True also unifies hamza forms and teh-marbuta — used for
    feature extraction and deduplication. The stored normalized text uses
    strong normalization (kept conservative on letters: hamza unification
    only).
    """
    text = normalize_unicode(text)
    text = "".join(ch for ch in text if ch not in _ZERO_WIDTH)
    text = remove_tatweel(text)
    text = remove_diacritics(text)
    text = normalize_numerals(text)
    text = normalize_punctuation(text)
    if strong:
        text = unify_hamza(text)
        text = unify_teh_marbuta(text)
    return collapse_whitespace(text)


# --------------------------------------------------------------------------
# Arabizi
# --------------------------------------------------------------------------

_ARABIC_CHARS = set("ابتثجحخدذرزسشصضطظعغفقكلمنهويءآأإؤئةى")


def is_arabic(text: str) -> bool:
    return any(ch in _ARABIC_CHARS for ch in text)


def arabic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(1 for ch in letters if "\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f")
    return arabic / len(letters)


def is_arabizi(text: str) -> bool:
    """Heuristic: latin-script text that looks like romanized Arabic."""
    if not text.strip():
        return False
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = sum(1 for ch in text if ch.isalpha())
    if total == 0:
        return False
    ratio = latin / total
    if ratio < 0.6:
        return False
    # Needs at least one arabizi marker to count (digits-as-letters or
    # romanized patterns), otherwise English text would be mislabeled.
    markers = re.findall(r"[2379'5]", text, re.IGNORECASE)
    romanized = re.findall(
        r"\b(ana|enta|kaif|shlon|shu|wen|lesh|laish|shway|kwayes|mabsut|wayn|inta|inti|eh|aywa|la2|3ala|fein|iza|eih|lein)\b",
        text,
        re.IGNORECASE,
    )
    return ratio >= 0.85 and (bool(markers) or bool(romanized))


def transliterate_arabizi(text: str) -> tuple[str, float]:
    """Best-effort Arabizi → Arabic transliteration with confidence."""
    words = text.split()
    out_words: list[str] = []
    for word in words:
        lowered = word.lower()
        out = lowered
        for src, dst in _TRANSLIT:
            out = out.replace(src, dst)
        out = "".join(_LATIN_MAP.get(ch, ch) for ch in out)
        out_words.append(out)
    result = " ".join(out_words)
    confidence = 0.55 + 0.1 * min(1.0, len(words) / 6)
    return result, confidence


# --------------------------------------------------------------------------
# Dialect lexicons
# --------------------------------------------------------------------------

# High-precision markers per dialect. Weights: 2.0 = very distinctive.
DIALECT_LEXICON: dict[str, dict[str, float]] = {
    "egyptian": {
        "إيه": 2.0, "ليه": 1.5, "فين": 1.5, "كده": 1.5, "أوي": 2.0,
        "دلوقتي": 1.5, "إزيك": 2.0, "عايز": 1.5, "برضه": 1.5, "بقة": 1.5,
        "بجد": 1.0, "شوية": 1.0, "خلاص": 1.0, "لسه": 1.5, "امبارح": 1.5,
        "بكرة": 1.0, "إمتى": 1.5, "ياخويا": 2.0, "يا معلم": 2.0, "اللي": 1.0,
        "كمان": 1.0, "مش": 0.8, "قوي": 0.8, "إنت": 0.8, "إحنا": 1.0,
        "إزيك": 2.0, "عامل إيه": 2.0, "تعالى": 1.0, "هروح": 1.0, "يلا": 0.8,
    },
    "saudi": {
        "وش": 2.0, "إيش": 2.0, "ليش": 1.5, "وشلون": 2.0, "الحين": 1.5,
        "توه": 1.5, "أبغى": 2.0, "أبي": 1.5, "وش ذا": 2.0, "مدري": 2.0,
        "عسى": 1.0, "إبغى": 2.0, "كفو": 2.0, "وش رايك": 2.0, "يلزم": 1.0,
        "بس": 0.8, "توي": 1.5, "من متى": 1.5, "زين": 0.8, "عساك": 1.0,
    },
    "gulf": {
        "شنو": 2.0, "شلون": 2.0, "ويه": 1.5, "دش": 1.5, "مابي": 1.5,
        "توني": 1.5, "هالحين": 1.5, "خوش": 1.5, "مرة": 0.8, "حيل": 1.5,
        "يمه": 2.0, "بوه": 2.0, "شكد": 1.5, "عيني": 1.0, "أوكي": 0.8,
        "زين": 0.8, "وين": 1.0, "ليش": 1.0, "يعني": 0.5,
    },
    "levantine": {
        "شو": 2.0, "شلون": 2.0, "كيفك": 2.0, "وين": 1.5, "مين": 1.5,
        "إيمتى": 1.5, "هلق": 2.0, "هلأ": 2.0, "بدي": 2.0, "بده": 2.0,
        "عم": 1.5, "رح": 1.5, "كتير": 1.5, "منيح": 2.0, "هيك": 1.5,
        "ليش": 1.5, "لسا": 1.5, "إجا": 1.5, "إمبارح": 1.5, "عشان": 1.0,
        "حلو": 1.0, "بس": 0.8, "خالص": 0.8, "عالأرض": 1.5,
    },
    "iraqi": {
        "هسه": 2.0, "دز": 2.0, "أكو": 2.0, "ماكو": 2.0, "هواية": 2.0,
        "شكد": 2.0, "أريد": 1.5, "تره": 2.0, "چان": 2.0, "گل": 2.0,
        "إدري": 1.5, "عيني": 1.0, "إجيت": 1.5, "راح": 0.8, "خل": 1.0,
        "شنو": 1.5, "شلونك": 1.5, "وين": 1.0, "لعد": 2.0, "بيه": 2.0,
    },
    "maghrebi": {
        "واش": 2.0, "شحال": 2.0, "علاش": 2.0, "دابا": 2.0, "دبا": 2.0,
        "واخا": 2.0, "زوين": 2.0, "بزاف": 2.0, "درهم": 1.5, "خويا": 2.0,
        "عافاك": 2.0, "ماشي": 1.5, "أش": 1.5, "شكون": 2.0, "كيفاش": 2.0,
        "تونس": 1.0, "المغرب": 1.0, "الجزائر": 1.0, "واخا": 2.0,
    },
    "msa": {
        "كيف حالك": 2.0, "ما اسمك": 2.0, "هل": 1.0, "أين": 1.5, "متى": 1.0,
        "لماذا": 1.5, "لأن": 1.0, "السلام عليكم": 1.5, "شكرا": 1.0,
        "من فضلك": 1.5, "لكن": 1.0, "أيضا": 1.0, "حيث": 1.0, "بينما": 1.0,
        "لذلك": 1.0, "عليكم": 1.0, "سوف": 1.0, "إن شاء الله": 1.0,
        "الحمد لله": 1.0, "نعم": 0.8, "لا": 0.5, "أنا": 0.8, "أنت": 0.8,
        "هذا": 1.0, "هذه": 1.0, "يرجى": 1.5, "مع": 0.8, "على": 0.5,
    },
}

DIALECT_LABELS = {
    "egyptian": "مصري",
    "saudi": "سعودي",
    "gulf": "خليجي",
    "levantine": "شامي",
    "iraqi": "عراقي",
    "maghrebi": "مغاربي",
    "msa": "فصحى",
    "arabizi": "عربيزي",
    "mixed": "مختلط",
    "unknown": "غير محدد",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,.;:!?()\[\]{}]+", text) if t]


def detect_dialect(text: str) -> dict[str, Any]:
    """Lexical dialect detection with honest confidence.

    Never forces a label: low scores → 'unknown'; two close dialects → 'mixed'.
    """
    if not text.strip():
        return {"label": "unknown", "confidence": 0.0, "scores": {}, "provider": "deterministic"}
    if is_arabizi(text):
        return {
            "label": "arabizi",
            "confidence": min(0.95, 0.7 + arabic_ratio(text) * 0.2),
            "scores": {"arabizi": 1.0},
            "provider": "deterministic",
            "arabizi": True,
        }
    norm = normalize_arabic(text, strong=True)
    tokens = tokenize(norm)
    joined = " " + norm + " "
    scores: dict[str, float] = {}
    for dialect, terms in DIALECT_LEXICON.items():
        score = 0.0
        for term, weight in terms.items():
            term_norm = normalize_arabic(term, strong=True)
            if term_norm in tokens:
                score += weight
            elif f" {term_norm} " in joined:
                score += weight * 0.8
            elif any(term_norm in t for t in tokens):
                # compound forms like وشلونكم / كيفكم / أبغى
                score += weight * 0.5
        if score > 0:
            scores[dialect] = score / max(1.0, len(tokens) ** 0.5)
    if not scores:
        return {"label": "unknown", "confidence": 0.0, "scores": {}, "provider": "deterministic"}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top, second = ranked[0], ranked[1] if len(ranked) > 1 else (None, 0.0)
    total = sum(v for v in scores.values() if v)
    if top[1] <= 0.0:
        return {"label": "unknown", "confidence": 0.0, "scores": scores, "provider": "deterministic"}
    confidence = top[1] / total if total > 0 else 0.0
    if second[1] and top[1] / max(second[1], 1e-6) < 1.25:
        return {
            "label": "mixed",
            "confidence": min(0.9, confidence),
            "scores": scores,
            "provider": "deterministic",
            "candidates": [top[0], second[0]],
        }
    return {"label": top[0], "confidence": min(0.95, confidence), "scores": scores, "provider": "deterministic"}


# --------------------------------------------------------------------------
# Intents
# --------------------------------------------------------------------------

INTENT_LEXICON: dict[str, list[str]] = {
    "greeting": ["السلام عليكم", "مرحبا", "أهلا", "هلا", "صباح الخير", "مساء الخير", "أهلا وسهلا"],
    "question": ["كيف", "ما هو", "ما هي", "لماذا", "هل", "متى", "أين", "ليش", "إيش", "شو", "واش", "إيه", "بكم", "كم"],
    "purchase": ["السعر", "كم سعر", "أريد شراء", "أرغب بشراء", "أطلب", "الطلب", "متوفر", "أحجز", "بكم", "شراء", "إشترا", "أشتري", "طلب"],
    "complaint": ["شكوى", "مشكلة", "بطيء", "سيئ", "خربان", "لا يعمل", "غلط", "زعلان", "مستاء", "أزعجني", "سيئة", "عطلان", "مضايق"],
    "support": ["مساعدة", "مشكلة تقنية", "كيف أفعل", "ساعدني", "عطل", "لا يعمل", "إعداد", "تسجيل الدخول", "استرجاع", "مشكلة في", "أحتاج مساعدة"],
    "praise": ["ممتاز", "رائع", "شكرا", "أحسنت", "جميل", "حلو", "زين", "عظيم", "أكثر من رائع", "مبدع"],
    "spam": ["اربح", "انضم الآن", "اضغط على الرابط", "عروض حصرية", "خصم 90", "وظائف من المنزل", "اشترك في القناة", "أرسل الرقم", "مكسب سريع", "رابط التحميل", "جائزة", "ربح 1000"],
    "escalation": ["محامي", "شكوى رسمية", "بلاغ", "تحذير", "وزارة", "قانوني", "مقاضاة", "دعوى", "حقوقي", "نقابة"],
}

INTENT_LABELS = {
    "greeting": "تحية",
    "question": "سؤال",
    "purchase": "شراء",
    "complaint": "شكوى",
    "support": "دعم فني",
    "praise": "إشادة",
    "spam": "إعلان/سبام",
    "escalation": "تصعيد",
    "unknown": "غير محدد",
}


def detect_intent(text: str) -> dict[str, Any]:
    norm = normalize_arabic(text, strong=True)
    tokens = tokenize(norm)
    joined = " " + norm + " "
    scores: dict[str, float] = {}
    for intent, terms in INTENT_LEXICON.items():
        score = 0.0
        for term in terms:
            t = normalize_arabic(term, strong=True)
            if t in tokens:
                score += 1.0
            elif f" {t} " in joined:
                score += 0.7
        if score > 0:
            scores[intent] = score
    if not scores:
        return {"label": "unknown", "confidence": 0.0, "scores": {}, "provider": "deterministic"}
    top = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values())
    return {"label": top[0], "confidence": top[1] / total, "scores": scores, "provider": "deterministic"}


# --------------------------------------------------------------------------
# Moderation
# --------------------------------------------------------------------------

MODERATION_CRITICAL = [
    "سأقتلك", "اقتلك", "اضربك", "أذبحك", "انقلع", "اخرس", "قحبة", "شرموط",
    "متناك", "ابن الكلب", "عاهرة", "قذر", "ابن الحرام", "يلعن", "لعنك الله",
    "أحمق", "غبي", "حقير", "خنزير", "حمار", "كلب", "تيس", "نذل", "خسيس",
    "افشل", "فاشل", "زبالة", "وسخ", "مخنث", "أبله", "بليد", "معتوه", "مجنون",
]
MODERATION_WARN = [
    "كذب", "كذاب", "سارق", "لص", "نصاب", "محتال", "وضيع", "مقرف", "مزعج",
    "تافه", "سخيف", "أبله", "ما تفهم", "انت غبي", "ما تعرف", "قلة أدب",
]
MODERATION_SPAM = [
    "اربح", "انضم الآن", "اضغط على الرابط", "عروض حصرية", "خصم 90",
    "وظائف من المنزل", "اشترك في القناة", "أرسل الرقم", "جائزة كبرى",
    "رابط التحميل", "ربح يومي", "مكسب سريع", "كلمة السر", "تحقق من حسابك",
]
MODERATION_PHISHING = ["كلمة السر", "الرقم السري", "بيانات البطاقة", "رمز التحقق", "تحقق من حسابك", "اضغط لتأكيد"]

SEVERITY_LABELS = {"critical": "حرِج", "warn": "تنبيه", "spam": "سبام", "privacy": "خصوصية"}


def _light_stem(word: str) -> str:
    """Strip Arabic clitics/affixes for lexical matching.

    Applied to both lexicon terms and message tokens so inflected forms
    (اللص، والكذاب، نصابين، حقيرة) collapse onto their base form, while
    unrelated words (خالص، الصبح) never false-positive on substrings.
    """
    w = word
    changed = True
    while changed and w:
        changed = False
        for prefix in ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ك", "ل"):
            if len(w) > len(prefix) + 1 and w.startswith(prefix):
                w = w[len(prefix):]
                changed = True
                break
    changed = True
    while changed and w:
        changed = False
        for suffix in ("ين", "ون", "ات", "هم", "هن", "كم", "نا", "ها", "ه"):
            if len(w) > len(suffix) + 1 and w.endswith(suffix):
                w = w[:-len(suffix)]
                changed = True
                break
    return w


def _term_hits(term: str, joined: str, stems: set[str]) -> bool:
    """Whole-word matching for single terms, containment for phrases."""
    if " " in term:
        return term in joined
    return _light_stem(term) in stems


def moderation_check(text: str) -> dict[str, Any]:
    """Returns {flags: [{severity, reason, matched}], decision, summary}."""
    norm = normalize_arabic(text, strong=True)
    stems = {_light_stem(t) for t in tokenize(norm) if t}
    flags: list[dict[str, Any]] = []

    for term in MODERATION_CRITICAL:
        if _term_hits(term, norm, stems):
            flags.append({"severity": "critical", "reason": "إساءة أو تهديد", "matched": term})
    for term in MODERATION_WARN:
        if _term_hits(term, norm, stems):
            flags.append({"severity": "warn", "reason": "أسلوب مهين", "matched": term})
    for term in MODERATION_SPAM:
        if _term_hits(term, norm, stems):
            flags.append({"severity": "spam", "reason": "رسالة ترويجية/احتيال", "matched": term})
    for term in MODERATION_PHISHING:
        if _term_hits(term, norm, stems):
            flags.append({"severity": "critical", "reason": "محاولة احتيال (تصيّد)", "matched": term})

    # privacy: shared personal data
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        flags.append({"severity": "privacy", "reason": "مشاركة بريد إلكتروني", "matched": "email"})
    if re.search(r"(?:\+?\d[\s-]?){8,}", text):
        flags.append({"severity": "privacy", "reason": "مشاركة رقم هاتف", "matched": "phone"})

    if not flags:
        return {"flags": [], "decision": "skip", "summary": "", "provider": "deterministic"}
    worst = "critical" if any(f["severity"] == "critical" for f in flags) else "warn"
    decision = "escalate" if worst == "critical" else "flag"
    summary = "؛ ".join(f"{SEVERITY_LABELS.get(f['severity'], f['severity'])}: {f['reason']}" for f in flags[:3])
    return {"flags": flags, "decision": decision, "summary": summary, "provider": "deterministic"}


# --------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------

_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\d{3}[\s-]?\d{3}[\s-]?\d{3,4}|\d{10,11})")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+")
_MENTION_RE = re.compile(r"@[\w\u0600-\u06ff]+")
_HASHTAG_RE = re.compile(r"#[\w\u0600-\u06ff]+")
_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ريال|جنيه|جنية|درهم|دينار|دولار|ليرة|يورو|فرنك)")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_CURRENCIES = {"ريال": "SAR", "جنيه": "EGP", "جنية": "EGP", "درهم": "AED", "دينار": "DIN", "دولار": "USD", "ليرة": "LYD", "يورو": "EUR", "فرنك": "TND"}


def extract_entities(text: str) -> dict[str, Any]:
    entities: dict[str, list[str]] = {
        "emails": [], "phones": [], "urls": [], "mentions": [], "hashtags": [],
        "prices": [], "times": [], "dates": [], "numbers": [],
    }
    text_norm = normalize_numerals(text)
    entities["emails"] = list(dict.fromkeys(_EMAIL_RE.findall(text)))
    entities["phones"] = [p for p in dict.fromkeys(_PHONE_RE.findall(text_norm)) if len(re.sub(r"\D", "", p)) >= 8]
    entities["urls"] = list(dict.fromkeys(_URL_RE.findall(text)))
    entities["mentions"] = list(dict.fromkeys(_MENTION_RE.findall(text)))
    entities["hashtags"] = list(dict.fromkeys(_HASHTAG_RE.findall(text)))
    for price in _PRICE_RE.findall(text_norm):
        entities["prices"].append(
            {"value": float(price[0].replace(",", ".")), "currency": _CURRENCIES.get(price[1], price[1])}
        )
    entities["times"] = list(dict.fromkeys(_TIME_RE.findall(text_norm)))
    entities["dates"] = list(dict.fromkeys(_DATE_RE.findall(text_norm)))
    entities["numbers"] = list(dict.fromkeys(re.findall(r"\b\d+\b", text_norm)))
    return entities


# --------------------------------------------------------------------------
# Quality
# --------------------------------------------------------------------------


def quality_score(text: str, *, dialect_confidence: float = 0.0) -> dict[str, Any]:
    """0..1 quality: language confidence, informativeness, length, variety."""
    if not text.strip():
        return {"score": 0.0, "reasons": ["فارغ"]}
    total = len(text)
    arabic = arabic_ratio(text)
    tokens = tokenize(normalize_arabic(text, strong=True))
    unique = len(set(tokens))
    reasons: list[str] = []
    score = 0.5
    if arabic >= 0.7:
        score += 0.2
    else:
        reasons.append("نسبة عربية منخفضة")
    if total >= 30:
        score += 0.15
    elif total < 10:
        score -= 0.15
        reasons.append("رسالة قصيرة")
    if unique >= 5:
        score += 0.1
    if dialect_confidence >= 0.5:
        score += 0.05
    if re.search(r"(https?://|www\.)", text):
        score -= 0.05
    score = max(0.0, min(1.0, score))
    return {"score": round(score, 3), "reasons": reasons, "language_confidence": round(arabic, 3)}


# --------------------------------------------------------------------------
# camel-tools optional enrichment
# --------------------------------------------------------------------------


def camel_features(text: str) -> dict[str, Any]:
    """Optional morphology features via camel-tools (self-hosted install).

    Returns {} when camel-tools is not installed. The lexical engine is the
    always-available fallback.
    """
    try:  # pragma: no cover - heavy optional dependency
        from camel_tools.tokenizers.word import simple_word_tokenize
        from camel_tools.utils.dediac import dediac_ar

        tokens = simple_word_tokenize(text)
        return {"tokens": [dediac_ar(t) for t in tokens[:50]], "provider": "camel_tools"}
    except Exception:
        return {}
