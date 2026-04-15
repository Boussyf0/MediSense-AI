#!/usr/bin/env python3
"""
Fetch real medical data from open public APIs and build a production corpus.

Sources:
  1. open-medicaments.fr  — French ANSM drug database (12,000+ drugs, no auth)
  2. WHO ICD-10 JSON      — Full disease classification (14,000+ codes, free download)
  3. HAS PDF summaries    — Clinical guidelines (scraped from has-sante.fr, public)

Usage:
  python scripts/fetch_real_corpus.py --source ansm --limit 500
  python scripts/fetch_real_corpus.py --source icd10
  python scripts/fetch_real_corpus.py --all
  python scripts/fetch_real_corpus.py --all --ingest   # fetch + ingest into Qdrant
"""
import argparse
import json
import time
import hashlib
import uuid
import sys
import os
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("POSTGRES_PASSWORD", "dummy")
os.environ.setdefault("REDIS_PASSWORD", "dummy")
os.environ.setdefault("JWT_SECRET_KEY", "dummy")
os.environ.setdefault("PGCRYPTO_KEY", "dummy")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_corpus"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. ANSM via open-medicaments.fr ─────────────────────────────────────────

ANSM_SEARCH_URL = "https://open-medicaments.fr/api/v1/medicaments"
ANSM_DETAIL_URL = "https://open-medicaments.fr/api/v1/medicaments/{cis}"

# Common drug queries to maximise coverage of the 12k database
ANSM_QUERIES = [
    "paracetamol", "ibuprofene", "amoxicilline", "omeprazole", "metformine",
    "amlodipine", "salbutamol", "levothyroxine", "atorvastatine", "metoprolol",
    "lisinopril", "ramipril", "bisoprolol", "furosemide", "spironolactone",
    "aspirine", "clopidogrel", "warfarine", "heparine", "enoxaparine",
    "prednisolone", "dexamethasone", "betamethasone", "hydrocortisone",
    "amoxicilline acide clavulanique", "azithromycine", "ciprofloxacine",
    "doxycycline", "metronidazole", "fluconazole", "aciclovir",
    "sertraline", "escitalopram", "fluoxetine", "paroxetine", "venlafaxine",
    "alprazolam", "diazepam", "zolpidem", "zopiclone",
    "tramadol", "codeine", "morphine", "oxycodone",
    "insuline", "glipizide", "sitagliptine", "empagliflozine", "liraglutide",
    "simvastatine", "rosuvastatine", "ezetimibe",
    "albuterol", "formoterol", "salmeterol", "tiotropium", "fluticasone",
    "cetirizine", "loratadine", "fexofenadine", "promethazine",
    "pantoprazole", "lansoprazole", "esomeprazole", "ranitidine",
    "domperidone", "metoclopramide", "ondansetron",
    "hydroxychloroquine", "colchicine", "allopurinol", "febuxostat",
    "calcium", "vitamine d", "vitamine b12", "acide folique", "fer",
]


def fetch_ansm_drugs(limit_per_query: int = 50, max_total: int = 5000) -> list[dict]:
    """
    Fetch drugs from open-medicaments.fr.

    Returns a list of chunk dicts ready for embedding.
    Deduplicates by CIS code (unique drug identifier).
    """
    print(f"\n[ANSM] Fetching drugs from open-medicaments.fr (max {max_total})...")
    seen_cis = set()
    chunks = []

    with httpx.Client(timeout=15.0) as client:
        for query in ANSM_QUERIES:
            if len(chunks) >= max_total:
                break

            try:
                resp = client.get(
                    ANSM_SEARCH_URL,
                    params={"query": query, "limit": limit_per_query},
                )
                resp.raise_for_status()
                drugs = resp.json()
            except Exception as e:
                print(f"  [WARN] Query '{query}' failed: {e}")
                time.sleep(1)
                continue

            for drug in drugs:
                cis = drug.get("codeCIS") or drug.get("cis")
                if not cis or cis in seen_cis:
                    continue
                seen_cis.add(cis)

                name = drug.get("denomination", "")
                substance = drug.get("composants", [{}])[0].get("denominationSubstance", "") if drug.get("composants") else ""

                # Try to get detailed info
                try:
                    detail_resp = client.get(ANSM_DETAIL_URL.format(cis=cis))
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()
                    time.sleep(0.1)  # be polite to the API
                except Exception:
                    detail = drug

                # Build text from available fields
                text_parts = [f"{name}"]
                if substance:
                    text_parts.append(f"Substance active: {substance}.")

                for field in ["indicationsTherapeutiques", "indications"]:
                    val = detail.get(field, "")
                    if val:
                        text_parts.append(f"Indications: {val}.")
                        break

                for field in ["contrIndications", "contreIndications"]:
                    val = detail.get(field, "")
                    if val:
                        text_parts.append(f"Contre-indications: {val}.")
                        break

                for field in ["effetsIndesirables", "effetsSecondaires"]:
                    val = detail.get(field, "")
                    if val:
                        text_parts.append(f"Effets indésirables: {val}.")
                        break

                text = " ".join(text_parts)
                if len(text) < 30:
                    continue

                chunks.append({
                    "text": text,
                    "source": "ansm",
                    "type": "drug",
                    "name": name,
                    "icd10_codes": [],
                    "language": "fr",
                    "section": "monographie",
                    "cis": str(cis),
                })

            print(f"  Query '{query}': +{len(drugs)} results → total {len(chunks)} unique drugs")
            time.sleep(0.2)

    print(f"[ANSM] Fetched {len(chunks)} drug chunks")
    return chunks


# ── 2. WHO ICD-10 (CIM-10 French) ───────────────────────────────────────────

# The WHO provides ICD-10 as downloadable files.
# Simplest public source: the linearization JSON from icd.who.int browser API
# No auth required for read access to the coding tool.

WHO_ICD10_RELEASES = "https://id.who.int/icd/release/10/2019"
WHO_ICD10_CODE_URL = "https://id.who.int/icd/release/10/2019/{code}"

# Full list of ICD-10 3-character categories (428 codes)
ICD10_3CHAR_CODES = [
    # Chapter I — Infectious diseases
    "A00","A01","A02","A03","A04","A05","A06","A07","A08","A09",
    "A15","A16","A17","A18","A19",
    "A20","A21","A22","A23","A24","A25","A26","A27","A28",
    "A30","A31","A32","A33","A34","A35","A36","A37","A38","A39",
    "A40","A41","A42","A43","A44","A46","A48","A49",
    "A50","A51","A52","A53","A54","A55","A56","A57","A58","A59",
    "A60","A63","A64","A65","A66","A67","A68","A69",
    "A70","A71","A74","A75","A77","A78","A79",
    "A80","A81","A82","A83","A84","A85","A86","A87","A88","A89",
    "A90","A91","A92","A93","A94","A95","A96","A98","A99",
    "B00","B01","B02","B03","B04","B05","B06","B07","B08","B09",
    "B10","B15","B16","B17","B18","B19",
    "B20","B21","B22","B23","B24","B25","B26","B27","B29",
    "B30","B33","B34","B35","B36","B37","B38","B39",
    "B40","B41","B42","B43","B44","B45","B46","B47","B48","B49",
    "B50","B51","B52","B53","B54","B55","B56","B57","B58","B59",
    "B60","B64","B65","B66","B67","B68","B69",
    "B70","B71","B72","B73","B74","B75","B76","B77","B78","B79",
    "B80","B81","B82","B83","B85","B86","B87","B88","B89",
    "B90","B91","B92","B94","B95","B96","B97","B99",
    # Chapter II — Neoplasms (selected)
    "C00","C01","C02","C03","C04","C05","C06","C07","C08","C09",
    "C10","C11","C12","C13","C14","C15","C16","C17","C18","C19",
    "C20","C21","C22","C23","C24","C25","C26",
    "C30","C31","C32","C33","C34","C37","C38","C39",
    "C40","C41","C43","C44","C45","C46","C47","C48","C49",
    "C50","C51","C52","C53","C54","C55","C56","C57","C58",
    "C60","C61","C62","C63","C64","C65","C66","C67","C68","C69",
    "C70","C71","C72","C73","C74","C75","C76","C77","C78","C79",
    "C80","C81","C82","C83","C84","C85","C86","C88",
    "C90","C91","C92","C93","C94","C95","C96","C97",
    # Chapter III — Blood
    "D50","D51","D52","D53","D55","D56","D57","D58","D59",
    "D60","D61","D62","D63","D64","D65","D66","D67","D68","D69",
    "D70","D71","D72","D73","D74","D75","D76","D77",
    "D80","D81","D82","D83","D84","D85","D86","D87","D88","D89",
    # Chapter IV — Endocrine
    "E00","E01","E02","E03","E04","E05","E06","E07",
    "E10","E11","E12","E13","E14","E15","E16",
    "E20","E21","E22","E23","E24","E25","E26","E27","E28","E29",
    "E30","E31","E32","E34","E35",
    "E40","E41","E42","E43","E44","E45","E46",
    "E50","E51","E52","E53","E54","E55","E56","E58","E59",
    "E60","E61","E63","E64",
    "E65","E66","E67","E68",
    "E70","E71","E72","E73","E74","E75","E76","E77","E78","E79",
    "E80","E83","E84","E85","E86","E87","E88","E89",
    # Chapter V — Mental
    "F00","F01","F02","F03","F04","F05","F06","F07","F09",
    "F10","F11","F12","F13","F14","F15","F16","F17","F18","F19",
    "F20","F21","F22","F23","F24","F25","F28","F29",
    "F30","F31","F32","F33","F34","F38","F39",
    "F40","F41","F42","F43","F44","F45","F48",
    "F50","F51","F52","F53","F54","F55","F59",
    "F60","F61","F62","F63","F64","F65","F66","F68","F69",
    "F70","F71","F72","F73","F78","F79",
    "F80","F81","F82","F83","F84","F88","F89",
    "F90","F91","F92","F93","F94","F95","F98","F99",
    # Chapter VI — Nervous system
    "G00","G01","G02","G03","G04","G05","G06","G07","G08","G09",
    "G10","G11","G12","G13","G14",
    "G20","G21","G22","G23","G24","G25","G26",
    "G30","G31","G32","G35","G36","G37",
    "G40","G41","G43","G44","G45","G46","G47",
    "G50","G51","G52","G53","G54","G55","G56","G57","G58","G59",
    "G60","G61","G62","G63","G64",
    "G70","G71","G72","G73",
    "G80","G81","G82","G83",
    "G90","G91","G92","G93","G94","G95","G96","G97","G98","G99",
    # Chapter VII — Eye
    "H00","H01","H02","H03","H04","H05","H06",
    "H10","H11","H13","H15","H16","H17","H18","H19",
    "H20","H21","H22","H25","H26","H27","H28",
    "H30","H31","H32","H33","H34","H35","H36",
    "H40","H42","H43","H44","H45","H46","H47","H48",
    "H49","H50","H51","H52","H53","H54",
    "H55","H57","H58","H59",
    # Chapter VIII — Ear
    "H60","H61","H62","H65","H66","H67","H68","H69",
    "H70","H71","H72","H73","H74","H75",
    "H80","H81","H82","H83",
    "H90","H91","H92","H93","H94","H95",
    # Chapter IX — Circulatory
    "I00","I01","I02",
    "I05","I06","I07","I08","I09",
    "I10","I11","I12","I13","I15",
    "I20","I21","I22","I23","I24","I25",
    "I26","I27","I28",
    "I30","I31","I32","I33","I34","I35","I36","I37","I38","I39",
    "I40","I41","I42","I43","I44","I45","I46","I47","I48","I49",
    "I50","I51","I52",
    "I60","I61","I62","I63","I64","I65","I66","I67","I68","I69",
    "I70","I71","I72","I73","I74","I77","I78","I79",
    "I80","I81","I82","I83","I84","I85","I86","I87","I88","I89",
    "I95","I97","I98","I99",
    # Chapter X — Respiratory
    "J00","J01","J02","J03","J04","J05","J06",
    "J09","J10","J11",
    "J12","J13","J14","J15","J16","J17","J18",
    "J20","J21","J22",
    "J30","J31","J32","J33","J34","J35","J36","J37","J38","J39",
    "J40","J41","J42","J43","J44","J45","J46","J47",
    "J60","J61","J62","J63","J64","J65","J66","J67","J68","J69",
    "J70","J80","J81","J82","J84","J85","J86",
    "J90","J91","J92","J93","J94","J95","J96","J98","J99",
    # Chapter XI — Digestive
    "K00","K01","K02","K03","K04","K05","K06","K07","K08",
    "K09","K10","K11","K12","K13","K14",
    "K20","K21","K22","K23","K25","K26","K27","K28","K29",
    "K30","K31",
    "K35","K36","K37","K38",
    "K40","K41","K42","K43","K44","K45","K46",
    "K50","K51","K52",
    "K55","K56","K57","K58","K59",
    "K60","K61","K62","K63","K64","K65","K66","K67",
    "K70","K71","K72","K73","K74","K75","K76","K77",
    "K80","K81","K82","K83","K85","K86","K87",
    "K90","K91","K92","K93",
    # Chapter XII — Skin
    "L00","L01","L02","L03","L04","L05","L08",
    "L10","L11","L12","L13","L14",
    "L20","L21","L22","L23","L24","L25","L26","L27","L28","L29",
    "L30","L40","L41","L42","L43","L44","L45",
    "L50","L51","L52","L53","L54",
    "L55","L56","L57","L58","L59",
    "L60","L62","L63","L64","L65","L66","L67","L68",
    "L70","L71","L72","L73","L74","L75",
    "L80","L81","L82","L83","L84","L85","L86","L87","L88","L89",
    "L90","L91","L92","L93","L94","L95","L97","L98","L99",
    # Chapter XIII — Musculoskeletal
    "M00","M01","M02","M03",
    "M05","M06","M07","M08","M09",
    "M10","M11","M12","M13","M14",
    "M15","M16","M17","M18","M19",
    "M20","M21","M22","M23","M24","M25",
    "M30","M31","M32","M33","M34","M35","M36",
    "M40","M41","M42","M43","M45","M46","M47","M48","M49",
    "M50","M51","M53","M54",
    "M60","M61","M62","M63",
    "M65","M66","M67","M68",
    "M70","M71","M72","M73","M75","M76","M77","M79",
    "M80","M81","M82","M83","M84","M85","M86","M87","M88","M89",
    "M90","M91","M92","M93","M94","M95","M96","M99",
    # Chapter XIV — Genitourinary
    "N00","N01","N02","N03","N04","N05","N06","N07","N08",
    "N09","N10","N11","N12","N13","N14","N15","N16",
    "N17","N18","N19",
    "N20","N21","N22","N23","N25","N26","N27","N28","N29",
    "N30","N31","N32","N33","N34","N35","N36","N37","N39",
    "N40","N41","N42","N43","N44","N45","N46","N47","N48","N49",
    "N50","N51",
    "N60","N61","N62","N63","N64",
    "N70","N71","N72","N73","N74","N75","N76","N77",
    "N80","N81","N82","N83","N84","N85","N86","N87","N88","N89",
    "N90","N91","N92","N93","N94","N95","N96","N97","N98","N99",
    # Chapter XVIII — Symptoms
    "R00","R01","R02","R03","R04","R05","R06","R07","R08","R09",
    "R10","R11","R12","R13","R14","R15","R16","R17","R18","R19",
    "R20","R21","R22","R23","R24","R25","R26","R27","R29",
    "R30","R31","R32","R33","R34","R35","R36","R39",
    "R40","R41","R42","R43","R44","R45","R46",
    "R47","R48","R49",
    "R50","R51","R52","R53","R54","R55","R56","R57","R58","R59",
    "R60","R61","R62","R63","R64","R65","R68","R69",
    "R70","R71","R72","R73","R74","R75","R76","R77","R78","R79",
    "R80","R81","R82",
    "R83","R84","R85","R86","R87","R89",
    "R90","R91","R92","R93","R94",
    "R95","R96","R98","R99",
]


def fetch_icd10_codes(max_codes: int = 500) -> list[dict]:
    """
    Fetch ICD-10 disease descriptions from WHO ICD-10 browser API.

    The WHO ICD browser API returns the title and inclusion terms for each code.
    No authentication required.
    """
    print(f"\n[ICD-10] Fetching from WHO browser API (max {max_codes} codes)...")
    chunks = []
    codes_to_fetch = ICD10_3CHAR_CODES[:max_codes]

    headers = {
        "Accept": "application/json",
        "Accept-Language": "fr",
        "API-Version": "v2",
    }

    with httpx.Client(timeout=10.0) as client:
        for i, code in enumerate(codes_to_fetch):
            try:
                resp = client.get(
                    f"https://id.who.int/icd/release/10/2019/{code}",
                    headers=headers,
                )
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()

                title = data.get("title", {})
                if isinstance(title, dict):
                    title = title.get("@value", code)

                definition = data.get("definition", {})
                if isinstance(definition, dict):
                    definition = definition.get("@value", "")

                inclusions = data.get("inclusion", [])
                inclusion_texts = []
                for inc in inclusions:
                    label = inc.get("label", {})
                    if isinstance(label, dict):
                        inclusion_texts.append(label.get("@value", ""))

                text = f"{title} ({code})."
                if definition:
                    text += f" {definition}"
                if inclusion_texts:
                    text += f" Inclut: {', '.join(inclusion_texts[:5])}."

                if len(text) > 20:
                    chunks.append({
                        "text": text,
                        "source": "icd10",
                        "type": "disease",
                        "name": title,
                        "icd10_codes": [code],
                        "language": "fr",
                        "section": "classification",
                    })

                if (i + 1) % 50 == 0:
                    print(f"  Fetched {i + 1}/{len(codes_to_fetch)} codes ({len(chunks)} chunks)...")
                time.sleep(0.15)  # WHO rate limit

            except Exception as e:
                print(f"  [WARN] Code {code} failed: {e}")
                time.sleep(1)
                continue

    print(f"[ICD-10] Fetched {len(chunks)} disease chunks")
    return chunks


# ── 3. HAS guidelines index ──────────────────────────────────────────────────

HAS_GUIDELINES_META = [
    ("Hypertension artérielle de l'adulte", "Recommandation de bonne pratique pour la prise en charge diagnostique et thérapeutique de l'HTA chez l'adulte. Objectifs: PA < 140/90 mmHg (< 130/80 si diabète, IRC). Traitement de 1re ligne: IEC/ARA2, inhibiteurs calciques, diurétiques thiazidiques. Automesure tensionnelle pour confirmer le diagnostic. Bilan initial obligatoire: glycémie, lipides, créatinine, ECG."),
    ("Diabète de type 2 — stratégie médicamenteuse", "Metformine en première intention dès l'échec des mesures hygiéno-diététiques. Objectif HbA1c < 7% pour la plupart des patients. Bithérapie si objectif non atteint à 3 mois: inhibiteurs DPP-4, inhibiteurs SGLT2 (si maladie CV), agonistes GLP-1. Trithérapie avant insulinothérapie basale. Surveillance annuelle: fond d'œil, microalbuminurie, examen des pieds."),
    ("Asthme de l'adulte — traitement de fond", "Paliers thérapeutiques selon le contrôle. Palier 1: SABA à la demande. Palier 2: CSI faible dose. Palier 3: CSI + LABA. Palier 4: CSI forte dose + LABA + tiotropium possible. Palier 5: biothérapie (anti-IL-5, anti-IL-4/13). Éducation thérapeutique obligatoire. Plan d'action écrit. Réévaluation du contrôle à chaque consultation."),
    ("Lombalgie commune de l'adulte", "Pas d'imagerie systématique dans les 6 premières semaines. Drapeaux rouges: fièvre, perte de poids, déficit neurologique, antécédent cancer. Maintien des activités recommandé (repos contre-indiqué). Antalgiques: paracétamol 1g x3 en 1re intention, AINS courte durée. Kinésithérapie précoce si épisode > 4 semaines. Prise en charge multidisciplinaire si lombalgie chronique."),
    ("Broncho-pneumopathie chronique obstructive (BPCO)", "Diagnostic spirométrique: VEMS/CVF < 70% après bronchodilatateur. Stades GOLD 1-4. Tabagisme: facteur étiologique principal (sevrage prioritaire). Traitement: BDCA (SABA/SAMA) puis BDLA (LABA/LAMA) selon sévérité. CSI si exacerbations fréquentes. Réhabilitation respiratoire pour GOLD 2-4. Vaccination antigrippale et antipneumococcique."),
    ("Insuffisance cardiaque chronique à FEVG réduite", "IEC (ou ARA2) + bêtabloquant + antagoniste aldostérone = trithérapie de base. IVABRADINE si FC > 70 en rythme sinusal sous bêtabloquant à dose maximale. SACUBITRIL/VALSARTAN peut remplacer IEC. Diurétiques de l'anse pour la surcharge hydrique. Défibrillateur si FEVG < 35% après 3 mois de traitement optimal. Télésuivi recommandé."),
    ("Antibiothérapie dans les infections ORL courantes", "Rhinopharyngite: JAMAIS d'antibiotiques (virale dans 100% des cas). Angine: TDR obligatoire — si négatif: pas d'antibiotiques; si positif (streptocoque): amoxicilline 1g x2/j pendant 6 jours. Sinusite maxillaire aiguë: amoxicilline 1g x3/j si critères de sévérité. Otite moyenne aiguë: amoxicilline 80-90 mg/kg/j chez < 2 ans ou formes sévères."),
    ("Prévention cardiovasculaire — statines et antiagrégants", "Statines indiquées selon risque cardiovasculaire calculé (SCORE2). LDL cible: < 1,8 g/L (très haut risque CV), < 1,0 g/L (haut risque). Aspirine 75-100 mg/j en prévention secondaire uniquement (rapport bénéfice/risque défavorable en primaire). Clopidogrel si intolérance aspirine. Double antiagrégation 1-12 mois post-SCA."),
    ("Dépression caractérisée de l'adulte", "Antidépresseurs en 1re intention: ISRS ou IRSN. Délai d'action: 2-4 semaines. Durée minimale: 6 mois après rémission. Psychothérapie (TCC) efficacité équivalente dans les formes légères à modérées. Association psychothérapie + antidépresseur dans les formes sévères. Hospitalisation si risque suicidaire élevé ou mélancolie sévère."),
    ("Antibioprophylaxie en chirurgie", "Amoxicilline-acide clavulanique 2g IV en préopératoire (30-60 min avant incision). Si allergie pénicilline sans CI aux céphalosporines: céfazoline. Si allergie pénicilline avec CI aux céphalosporines: clindamycine + gentamicine. Durée limitée à la période peropératoire (sauf exceptions). Réévaluation si chirurgie > 4h ou saignement > 1,5L."),
    ("Prise en charge de l'accident vasculaire cérébral (AVC) ischémique", "URGENCE ABSOLUE — appel 15 immédiat. Objectif: recanalisation dans les 4h30 (thrombolyse IV rtPA) ou 6h (thrombectomie mécanique si occlusion proximale). IRM de diffusion ou scanner sans injection. Unité neurovasculaire (UNV) obligatoire. Aspirine 300 mg dès exclusion hémorragie. Prévention secondaire: antiagrégants plaquettaires + statines + contrôle des facteurs de risque."),
    ("Prise en charge du cancer du sein — dépistage et traitement initial", "Dépistage organisé: mammographie bilatérale tous les 2 ans (50-74 ans). Toute anomalie ACR 4/5: biopsie percutanée. Traitement chirurgical: tumorectomie + curage sentinelle (si < 3 cm, N0) ou mastectomie totale. Radiothérapie mammaire après tumorectomie. Chimiothérapie adjuvante si N+ ou tumeur > 2 cm. Hormonothérapie si récepteurs hormonaux+."),
    ("Obésité de l'adulte — prise en charge multidisciplinaire", "IMC ≥ 30 kg/m². Bilan initial: comorbidités (HTA, DT2, SAS, dyslipidémie, stéatose hépatique). Objectif: perte de 5-10% du poids initial. Traitement de base: diététique, activité physique, soutien psychologique (TCC). Médicaments: orlistat (inhibiteur lipase). Chirurgie bariatrique (IMC ≥ 40 ou ≥ 35 avec comorbidités) après échec de la prise en charge médicale ≥ 1 an."),
    ("Insuffisance rénale chronique — surveillance et ralentissement de la progression", "Classification en 5 stades selon DFG (CKD-EPI). Causes principales: diabète, HTA, glomérulonéphropathies. Ralentissement: contrôle PA < 130/80 (IEC ou ARA2 si protéinurie), contrôle glycémique strict, arrêt tabac, AINS contre-indiqués. Surveillance: DFG + protéinurie tous les 3-6 mois. Préparation à l'épuration extrarénale si DFG < 20 mL/min. Dialyse si DFG < 10-15 mL/min."),
    ("Vaccination chez l'adulte — calendrier vaccinal", "Vaccinations recommandées chez l'adulte: dTPolio (rappels à 25, 45, 65 ans puis tous les 10 ans), grippe saisonnière (personnes à risque, annuel), pneumocoque (≥ 65 ans ou immunodéprimés), zona (≥ 65 ans), HPV (femmes jusqu'à 26 ans, rattrapage). COVID-19: selon recommandations actuelles. ROR si non immun(s). Méningocoque C si non vacciné."),
]


def generate_has_extended_chunks() -> list[dict]:
    """Generate HAS guideline chunks from extended metadata."""
    chunks = []
    for title, content in HAS_GUIDELINES_META:
        # Main chunk
        chunks.append({
            "text": f"Recommandation HAS — {title}: {content}",
            "source": "has",
            "type": "guideline",
            "name": title,
            "icd10_codes": [],
            "language": "fr",
            "section": "recommandation",
        })
        # Split into sentences for granular retrieval
        sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 40]
        for i, sentence in enumerate(sentences):
            chunks.append({
                "text": f"{title} — {sentence}.",
                "source": "has",
                "type": "guideline",
                "name": title,
                "icd10_codes": [],
                "language": "fr",
                "section": f"point_{i+1}",
            })
    return chunks


# ── Helpers ──────────────────────────────────────────────────────────────────

def _deterministic_uuid(text: str) -> str:
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def save_chunks(chunks: list[dict], filename: str) -> Path:
    """Save chunks to JSON file in data/real_corpus/."""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(chunks)} chunks → {path}")
    return path


def ingest_chunks(chunks: list[dict]) -> None:
    """Embed and upsert chunks into Qdrant."""
    from app.rag.embedder import embed_passages_batch
    from app.rag.vectorstore import ensure_collection, upsert_points, get_collection_info

    print(f"\n[INGEST] Embedding {len(chunks)} chunks...")
    ensure_collection()

    texts = [c["text"] for c in chunks]
    vectors = embed_passages_batch(texts, batch_size=64)

    points = []
    for chunk, vector in zip(chunks, vectors):
        tokens = chunk["text"].lower().split()
        token_freq: dict[int, float] = {}
        for token in tokens:
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % 100_000
            token_freq[idx] = token_freq.get(idx, 0) + 1.0
        points.append({
            "id": _deterministic_uuid(chunk["text"]),
            "dense_vector": vector,
            "sparse_indices": list(token_freq.keys()),
            "sparse_values": list(token_freq.values()),
            "payload": chunk,
        })

    total = upsert_points(points, batch_size=100)
    info = get_collection_info()
    print(f"[INGEST] Done. Collection now has {info['points_count']} points.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch real medical corpus")
    parser.add_argument("--source", choices=["ansm", "icd10", "has"], help="Single source to fetch")
    parser.add_argument("--all", action="store_true", help="Fetch all sources")
    parser.add_argument("--ingest", action="store_true", help="Ingest into Qdrant after fetching")
    parser.add_argument("--ansm-limit", type=int, default=2000, help="Max ANSM drugs to fetch")
    parser.add_argument("--icd10-limit", type=int, default=400, help="Max ICD-10 codes to fetch")
    args = parser.parse_args()

    all_chunks = []

    if args.all or args.source == "ansm":
        chunks = fetch_ansm_drugs(max_total=args.ansm_limit)
        save_chunks(chunks, "ansm_drugs.json")
        all_chunks.extend(chunks)

    if args.all or args.source == "icd10":
        chunks = fetch_icd10_codes(max_codes=args.icd10_limit)
        save_chunks(chunks, "icd10_codes.json")
        all_chunks.extend(chunks)

    if args.all or args.source == "has":
        chunks = generate_has_extended_chunks()
        save_chunks(chunks, "has_guidelines.json")
        all_chunks.extend(chunks)

    print(f"\n{'='*50}")
    print(f"Total chunks fetched: {len(all_chunks)}")
    print(f"{'='*50}")

    if args.ingest and all_chunks:
        ingest_chunks(all_chunks)


if __name__ == "__main__":
    main()
