"""
Language validator — enforces the language requirement from plan.language
and merchant.identity.languages / customer.identity.language_pref.

Hindi-English mix is the most common gap: production Vera often falls back
to pure English when the merchant prefers hi-en. We catch that here.

Detection strategy:
- "en"           → must look mostly Latin/ASCII; pass.
- "hi-en mix"    → must contain at least 1 Hindi token (transliterated)
                   OR Devanagari character (U+0900–U+097F).
- "te-en mix"    → must contain at least 1 Telugu char (U+0C00–U+0C7F)
                   OR transliterated Telugu token.
- "kn-en mix"    → Kannada char (U+0C80–U+0CFF) OR transliterated token.
- "mr-en mix"    → Devanagari (Marathi shares it) OR transliterated token.
- "ta-en mix"    → Tamil char (U+0B80–U+0BFF) OR transliterated token.
"""

from __future__ import annotations

import re
from typing import Any

# Common Hindi code-mix tokens (case-insensitive). Tight list — only words
# unlikely to be confused with English. Longer/multi-syllable preferred.
HINDI_TOKENS = {
    # Verbs / auxiliaries
    "hai", "hain", "hoga", "hogi", "hota", "hoti", "hote", "hua", "hui",
    "raha", "rahi", "rahe", "rahega", "rahegi", "tha", "thi", "the",
    "kar", "karte", "karega", "karegi", "karein", "karo", "kiya", "kijiye",
    "diya", "dijiye", "dega", "degi", "lijiye", "lega", "legi",
    "milega", "milegi", "milta", "milti", "milne", "lagega", "lagegi",
    "lagta", "lagti", "rakhne", "rakhna", "samajh", "samjha",
    # Pronouns / possessives
    "aap", "aapko", "aapke", "aapka", "aapki", "aapne", "apne", "apko",
    "apke", "apka", "apki", "humara", "tumhara", "iska", "uska",
    # Common modifiers / connectives
    "kyun", "kya", "kaise", "kab", "kahan", "lekin", "magar", "kyunki",
    "isliye", "agar", "warna", "phir", "fir", "abhi", "thoda", "bahut",
    "accha", "achha", "sahi", "theek", "badhiya", "shukriya", "dhanyawad",
    "namaste", "namaskar", "chalega", "chahiye", "shayad", "zaroor",
    # Salutations / honorifics
    "saheb", "sahab", "didi", "bhaiya", "bhai", "behenji",
    # Time / day
    "subah", "sham", "raat", "din", "kal", "aaj",
    # Numbers (used in mixed phrases)
    "ek", "ek-do", "do-teen",
    # Particles (common, slightly riskier so use selectively)
    "wala", "wali", "wale", "khud",
}

TELUGU_TOKENS = {
    "meeru", "meeku", "meeki", "naaku", "naa", "nenu", "vunnaaru",
    "vundi", "ledu", "kaadu", "andi", "ipudu", "ippudu", "tarvata",
    "manchidi", "santhosham", "dhanyavaadalu", "namaskaram",
    "ela", "ekkada", "evaru", "yenni", "etla",
}

KANNADA_TOKENS = {
    "namma", "nimage", "naanu", "neevu", "neenu", "ninage",
    "ide", "alva", "yake", "yaaru", "channagide", "innu",
    "namaskara", "dhanyavaada", "alli", "illi", "hege",
}

TAMIL_TOKENS = {
    "neenga", "naan", "naanga", "ungaluku", "enaku", "irukku",
    "varum", "vandhuten", "iruken", "panrenne", "panren",
    "vanakkam", "nanri",
}


# Script ranges (start, end inclusive)
_SCRIPTS: dict[str, tuple[int, int]] = {
    "devanagari": (0x0900, 0x097F),
    "telugu": (0x0C00, 0x0C7F),
    "kannada": (0x0C80, 0x0CFF),
    "tamil": (0x0B80, 0x0BFF),
    "bengali": (0x0980, 0x09FF),
}


def _has_script(text: str, script: str) -> bool:
    lo, hi = _SCRIPTS[script]
    return any(lo <= ord(ch) <= hi for ch in text)


def _has_token(text: str, tokens: set[str]) -> bool:
    lower = text.lower()
    # Use word boundaries — tokens must appear as standalone words
    for tok in tokens:
        if re.search(rf"\b{re.escape(tok)}\b", lower):
            return True
    return False


def check(
    body: str,
    *,
    plan: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body:
        return True, None, None, body

    target = (plan or {}).get("language") or _default_target(merchant, customer)
    target = target.lower().strip()

    if target == "en" or target == "":
        return True, None, None, body

    if "hi" in target or "mr" in target:
        # Hindi or Marathi mix — both use Devanagari OR transliterated Hindi tokens
        if _has_script(body, "devanagari") or _has_token(body, HINDI_TOKENS):
            return True, None, None, body
        return _fail_lang(target, "Hindi (e.g. 'apke liye 2 slots ready hain', 'theek hai')")

    if "te" in target:
        if _has_script(body, "telugu") or _has_token(body, TELUGU_TOKENS):
            return True, None, None, body
        return _fail_lang(target, "Telugu (e.g. 'meeku', 'manchidi')")

    if "kn" in target:
        if _has_script(body, "kannada") or _has_token(body, KANNADA_TOKENS):
            return True, None, None, body
        return _fail_lang(target, "Kannada (e.g. 'namaskara', 'channagide')")

    if "ta" in target:
        if _has_script(body, "tamil") or _has_token(body, TAMIL_TOKENS):
            return True, None, None, body
        return _fail_lang(target, "Tamil (e.g. 'vanakkam', 'irukku')")

    if "bn" in target:
        if _has_script(body, "bengali"):
            return True, None, None, body
        return _fail_lang(target, "Bengali")

    # Unknown language code — pass through
    return True, None, None, body


def _fail_lang(target: str, hint: str) -> tuple[bool, str, str, str]:
    return (
        False,
        f"Language mismatch: required '{target}' but body has no {hint} tokens or script.",
        f"Re-draft including natural code-mix in {hint}. "
        f"Use Hindi for warmth + transition phrases (e.g. 'apke liye', 'jab time mile reply karein'). "
        f"Do NOT translate the entire message — only mix in 2-4 native words/phrases naturally.",
        "",
    )


def _default_target(merchant: dict[str, Any] | None, customer: dict[str, Any] | None) -> str:
    if customer:
        pref = (customer.get("identity") or {}).get("language_pref")
        if pref:
            return pref
    langs = ((merchant or {}).get("identity") or {}).get("languages") or ["en"]
    if "hi" in langs:
        return "hi-en mix"
    if "te" in langs:
        return "te-en mix"
    if "kn" in langs:
        return "kn-en mix"
    if "mr" in langs:
        return "mr-en mix"
    if "ta" in langs:
        return "ta-en mix"
    return "en"
