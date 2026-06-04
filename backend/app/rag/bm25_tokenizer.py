"""
BM25 tokenizer — shared between query-time (vectorstore.py) and index-time
(ingest_medical_corpus.py) to guarantee sparse vector alignment.

Improvements over naive whitespace split:
  1. French medical stopword removal (~40 high-frequency function words)
  2. Unicode accent stripping ("céphalée" → "cephalee")
  3. Clinical bigram injection ("insuffisance cardiaque" → extra token)
  4. Punctuation stripping and length filtering (drop tokens ≤ 1 char)
"""
import hashlib
import re
import unicodedata

from qdrant_client.models import SparseVector


# ── French stopwords (high TF, zero clinical signal) ───────
FRENCH_STOPWORDS: frozenset[str] = frozenset({
    "de", "du", "des", "le", "la", "les", "un", "une",
    "et", "ou", "en", "au", "aux", "ce", "ces", "se",
    "que", "qui", "ne", "pas", "par", "pour", "sur",
    "avec", "dans", "est", "son", "sont", "ont", "ete",
    "plus", "peut", "mais", "comme", "chez", "cette",
    "entre", "leurs", "tout", "tous", "elle", "il",
    "a", "d", "l", "n", "s", "y",
})

# ── Clinical bigrams (compound medical terms) ─────────────
# When both words appear adjacent, we inject an extra token for the
# compound so BM25 can match the phrase, not just individual words.
CLINICAL_BIGRAMS: list[tuple[str, str]] = [
    ("insuffisance", "cardiaque"),
    ("insuffisance", "renale"),
    ("insuffisance", "hepatique"),
    ("insuffisance", "respiratoire"),
    ("embolie", "pulmonaire"),
    ("douleur", "thoracique"),
    ("douleurs", "thoraciques"),
    ("fibrillation", "auriculaire"),
    ("hypertension", "arterielle"),
    ("diabete", "type"),
    ("accident", "vasculaire"),
    ("avc", "hemorragique"),
    ("avc", "ischemique"),
    ("infarctus", "myocarde"),
    ("arret", "cardiaque"),
    ("crise", "asthme"),
    ("angine", "poitrine"),
    ("ulcere", "gastrique"),
    ("cancer", "poumon"),
    ("cancer", "sein"),
    ("depression", "majeure"),
    ("diarrhee", "aigue"),
    ("fievre", "persistante"),
    ("cephalee", "intense"),
    ("toux", "seche"),
    ("douleur", "abdominale"),
    ("fosse", "iliaque"),
    ("prise", "charge"),
    ("effets", "secondaires"),
    ("effets", "indesirables"),
    ("traitement", "fond"),
    ("premiere", "intention"),
]

# Precompute hashed bigram tokens for fast lookup
_BIGRAM_SET: set[tuple[str, str]] = set(CLINICAL_BIGRAMS)

# Hash modulus — must match across query and index
_HASH_MOD = 100_000

# Regex to strip non-alphanumeric (keep hyphens inside words)
_PUNCT_RE = re.compile(r"[^\w\-]", re.UNICODE)


def strip_accents(text: str) -> str:
    """Remove diacritical marks: é→e, ç→c, ü→u, etc."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def tokenize_for_bm25(text: str) -> list[str]:
    """
    Tokenize text for BM25 sparse indexing/querying.

    Steps:
      1. Lowercase + strip accents
      2. Remove punctuation
      3. Split on whitespace
      4. Remove stopwords and single-char tokens
      5. Inject bigram tokens for clinical compounds
    """
    # Normalize
    cleaned = strip_accents(text.lower())
    cleaned = _PUNCT_RE.sub(" ", cleaned)

    # Split + filter
    raw_tokens = cleaned.split()
    tokens = [t for t in raw_tokens if len(t) > 1 and t not in FRENCH_STOPWORDS]

    # Inject bigrams
    bigram_tokens: list[str] = []
    for i in range(len(raw_tokens) - 1):
        a = raw_tokens[i] if raw_tokens[i] not in FRENCH_STOPWORDS else ""
        b = raw_tokens[i + 1] if raw_tokens[i + 1] not in FRENCH_STOPWORDS else ""
        pair = (strip_accents(raw_tokens[i]), strip_accents(raw_tokens[i + 1]))
        if pair in _BIGRAM_SET:
            bigram_tokens.append(f"{pair[0]}_{pair[1]}")

    return tokens + bigram_tokens


def compute_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """
    Compute a deterministic sparse TF vector for BM25.

    Uses md5 hashing (stable across processes/platforms) on cleaned tokens.
    Returns (indices, values) suitable for Qdrant SparseVector.
    """
    tokens = tokenize_for_bm25(text)
    token_freq: dict[int, float] = {}
    for token in tokens:
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % _HASH_MOD
        token_freq[idx] = token_freq.get(idx, 0.0) + 1.0

    return list(token_freq.keys()), list(token_freq.values())


def build_sparse_query(text: str) -> SparseVector | None:
    """
    Build a Qdrant SparseVector for query-time BM25 matching.

    Returns None if no tokens survive filtering.
    """
    indices, values = compute_sparse_vector(text)
    if not indices:
        return None
    return SparseVector(indices=indices, values=values)
