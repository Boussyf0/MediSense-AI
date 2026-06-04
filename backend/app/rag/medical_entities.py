"""
Medical entity extraction — maps patient symptoms to ICD-10 codes.

Used for:
  1. Qdrant payload filtering (boost relevant chunks)
  2. MCP drug name extraction (trigger ANSM lookup)
  3. Urgency detection (cardiac, respiratory, neurological)

This is a rule-based extractor (not ML). For a PFE scope, keyword matching
on a curated symptom→ICD-10 map is sufficient and deterministic.
"""
from dataclasses import dataclass

# Symptom → ICD-10 code mapping (most common clinical scenarios)
SYMPTOM_ICD10_MAP: dict[str, list[str]] = {
    # Cardiac
    "douleur thoracique": ["I20", "I21", "R07.9"],
    "douleur poitrine": ["I20", "I21", "R07.9"],
    "palpitations": ["R00.2"],
    "tachycardie": ["R00.0"],
    # Respiratory
    "dyspnee": ["R06.0"],
    "difficulte respiratoire": ["R06.0"],
    "essoufflement": ["R06.0"],
    "toux": ["R05"],
    "asthme": ["J45"],
    # Neurological
    "cephalee": ["R51"],
    "mal de tete": ["R51"],
    "migraine": ["G43"],
    "vertige": ["R42"],
    "perte de connaissance": ["R55"],
    "paralysie": ["G83"],
    # Gastrointestinal
    "douleur abdominale": ["R10"],
    "nausee": ["R11"],
    "vomissement": ["R11"],
    "diarrhee": ["K59.1"],
    # Musculoskeletal
    "douleur articulaire": ["M25.5"],
    "lombalgie": ["M54.5"],
    "mal de dos": ["M54.5"],
    # General
    "fievre": ["R50"],
    "fatigue": ["R53"],
    "insomnie": ["G47.0"],
    "allergie": ["T78.4"],
    "diabete": ["E11"],
    "hypertension": ["I10"],
    "grossesse": ["Z33"],
}

# Common drug names (trigger ANSM MCP lookup)
DRUG_KEYWORDS = {
    "doliprane", "paracetamol", "ibuprofene", "ibuprofène", "aspirine", "amoxicilline",
    "augmentin", "voltarene", "diclofenac", "omeprazole", "metformine",
    "amlodipine", "atorvastatine", "levothyrox", "ventoline", "salbutamol",
    "codeine", "tramadol", "prednisolone", "cortisone", "insuline",
    "warfarine", "warfarin", "antibiotique", "antibiotic",
}

# Urgency keywords — always trigger immediate warning
URGENCY_KEYWORDS = {
    "douleur thoracique", "douleur poitrine", "crise cardiaque",
    "difficulte respiratoire", "dyspnee", "etouffe", "ne respire",
    "perte de connaissance", "perdu connaissance", "syncope", "evanouissement",
    "paralysie faciale", "avc", "accident vasculaire",
    "hemorragie", "saignement abondant",
    "convulsion", "crise epileptique",
}


@dataclass
class ExtractedEntities:
    """Structured output of entity extraction."""
    icd10_codes: list[str]
    drug_names: list[str]
    is_urgent: bool
    matched_symptoms: list[str]


def extract_entities(text_fr: str) -> ExtractedEntities:
    """
    Extract medical entities from a French clinical query.

    Args:
        text_fr: The query normalized to French (output of normalizer.py).

    Returns:
        ExtractedEntities with ICD-10 codes, drug names, urgency flag.
    """
    text_lower = text_fr.lower()
    icd10_codes: list[str] = []
    matched_symptoms: list[str] = []

    # Match symptoms → ICD-10
    for symptom, codes in SYMPTOM_ICD10_MAP.items():
        if symptom in text_lower:
            icd10_codes.extend(codes)
            matched_symptoms.append(symptom)

    # Deduplicate ICD-10 codes
    icd10_codes = list(dict.fromkeys(icd10_codes))

    # Extract drug names
    drug_names = [drug for drug in DRUG_KEYWORDS if drug in text_lower]

    # Check urgency
    is_urgent = any(kw in text_lower for kw in URGENCY_KEYWORDS)

    return ExtractedEntities(
        icd10_codes=icd10_codes,
        drug_names=drug_names,
        is_urgent=is_urgent,
        matched_symptoms=matched_symptoms,
    )
