import re


def detect_language(text: str) -> str:
    """Detect if text is Bangla, Banglish, or English.

    Returns: 'bangla', 'banglish', or 'english'
    """
    # Check for Bengali Unicode characters (U+0980-U+09FF)
    bangla_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total = bangla_chars + latin_chars

    if total == 0:
        return "english"

    bangla_ratio = bangla_chars / total

    if bangla_ratio > 0.3:
        return "bangla"

    # Banglish detection: Latin script with common Bangla transliteration patterns
    banglish_patterns = [
        r'\bami\b', r'\btumi\b', r'\bapni\b', r'\bkemon\b', r'\bkoto\b',
        r'\bki\b', r'\bkothay\b', r'\bdao\b', r'\bdin\b', r'\bprice\b',
        r'\bproduct\b', r'\border\b', r'\bdite\b', r'\bchay\b', r'\bchai\b',
        r'\blagbe\b', r'\bkena\b', r'\bkinbo\b', r'\bkinte\b', r'\bdibo\b',
        r'\bpabo\b', r'\bache\b', r'\bnai\b', r'\bhobe\b', r'\bkorbo\b',
        r'\bbolun\b', r'\bbhai\b', r'\bapa\b', r'\bdada\b',
        r'\bdelivery\b', r'\bdhaka\b', r'\btaka\b', r'\bpathao\b',
        r'\bkobe\b', r'\bpele\b', r'\bkhoti\b', r'\bsaree\b', r'\bshopno\b',
    ]

    banglish_count = sum(
        1 for p in banglish_patterns if re.search(p, text.lower())
    )

    if banglish_count >= 2:
        return "banglish"

    return "english"
