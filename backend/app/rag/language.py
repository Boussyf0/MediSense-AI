"""
Language detection for MediSense chatbot.

Supports: French (fr), Arabic MSA (ar), Moroccan Darija (darija).

Strategy:
  1. Check script — Arabic characters → AR or Darija
  2. For Arabic script: check Darija markers (dialectal words)
  3. For Latin script: run langdetect, then check Darija Latin markers (Arabizi)
  4. Fallback: French

Why not use langdetect alone?
  - langdetect doesn't distinguish Darija from MSA
  - Darija written in Latin script (Arabizi) is detected as random languages
  - We need a hybrid: langdetect for FR/AR base + stopword heuristic for Darija
"""
import re
import unicodedata
from pathlib import Path
from functools import lru_cache

from langdetect import detect, DetectorFactory

# Make langdetect deterministic
DetectorFactory.seed = 42

# Supported languages
FRENCH = "fr"
ARABIC = "ar"
DARIJA = "darija"

# Arabic Unicode block range
_ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")

# Minimum ratio of Arabic characters to classify as Arabic script
_ARABIC_SCRIPT_THRESHOLD = 0.3

# Minimum number of Darija markers to classify as Darija
_DARIJA_MARKER_THRESHOLD = 2


@lru_cache(maxsize=1)
def _load_darija_stopwords() -> tuple[set[str], set[str]]:
    """Load Darija stopwords, split into Latin and Arabic sets."""
    stopwords_path = Path(__file__).resolve().parent.parent.parent / "data" / "darija_stopwords.txt"
    latin_words: set[str] = set()
    arabic_words: set[str] = set()

    with open(stopwords_path, encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            if _ARABIC_PATTERN.search(word):
                arabic_words.add(word)
            else:
                latin_words.add(word.lower())

    return latin_words, arabic_words


def _arabic_char_ratio(text: str) -> float:
    """Fraction of characters that are Arabic script."""
    if not text:
        return 0.0
    arabic_count = len(_ARABIC_PATTERN.findall(text))
    # Count only actual characters (not spaces/punctuation)
    letter_count = sum(1 for c in text if unicodedata.category(c).startswith("L"))
    if letter_count == 0:
        return 0.0
    return arabic_count / letter_count


def _count_darija_markers(tokens: list[str], marker_set: set[str]) -> int:
    """Count how many tokens match Darija markers (exact or substring)."""
    count = 0
    for token in tokens:
        # Exact match
        if token in marker_set:
            count += 1
            continue
        # Substring: Darija verb prefixes (ka-, kan-, kat-, kay-, gha-, ghad-)
        # and conjunctions get attached to words
        for marker in marker_set:
            if len(marker) >= 3 and (marker in token or token.startswith(marker)):
                count += 1
                break
    return count


def detect_language(text: str) -> str:
    """
    Detect the language of the input text.

    Returns one of: 'fr', 'ar', 'darija'.

    Detection logic:
      - If >= 30% Arabic characters → check for Darija Arabic markers
        → if >= 2 markers → Darija
        → else → Arabic (MSA)
      - If Latin script → run langdetect
        → if detected 'ar' → Arabic
        → check Darija Latin markers (Arabizi)
          → if >= 2 markers → Darija
        → if detected 'fr' → French
        → else → French (fallback)
    """
    text = text.strip()
    if not text:
        return FRENCH

    arabic_ratio = _arabic_char_ratio(text)
    latin_darija, arabic_darija = _load_darija_stopwords()

    # Arabic script path
    if arabic_ratio >= _ARABIC_SCRIPT_THRESHOLD:
        tokens = text.split()
        darija_count = _count_darija_markers(tokens, arabic_darija)
        if darija_count >= _DARIJA_MARKER_THRESHOLD:
            return DARIJA
        return ARABIC

    # Latin script path
    tokens = [t.lower().strip(".,!?;:'\"()") for t in text.split()]

    # Check Darija Arabizi markers first (langdetect fails on these)
    darija_count = _count_darija_markers(tokens, latin_darija)
    if darija_count >= _DARIJA_MARKER_THRESHOLD:
        return DARIJA

    # Fall back to langdetect
    try:
        detected = detect(text)
        if detected == "ar":
            return ARABIC
        if detected == "fr":
            return FRENCH
    except Exception:
        pass

    return FRENCH
