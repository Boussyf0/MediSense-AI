#!/usr/bin/env python3
"""
Build a Morocco-specific medical corpus.

Data sources:
  1. medicament.ma   — Moroccan drug registry (DMP/Ministère de la Santé)
                       5,435+ drugs, PPV in MAD, princeps/générique, distributeur
  2. simple-icd-10   — Full ICD-10 (12,542 codes, universal WHO standard)
  3. Moroccan health guidelines — Priority pathologies per Ministère de la Santé Maroc
                       (HTA, diabète, tuberculose, etc. — top burden of disease in Morocco)

Run on HOST machine (has internet):
  pip install simple-icd-10 httpx beautifulsoup4
  cd backend
  python scripts/build_moroccan_corpus.py

Then ingest inside Docker:
  docker exec medisense_fastapi python scripts/ingest_from_files.py
"""
import json
import hashlib
import uuid
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_corpus"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MEDICAMENT_MA_BASE = "https://medicament.ma/index.php"


# ── 1. Moroccan drugs from medicament.ma ─────────────────────────────────────

# Common drug names to search (DCI names — same active substance, different Moroccan brand names)
DRUG_QUERIES = [
    "paracetamol", "ibuprofene", "amoxicilline", "metformine", "amlodipine",
    "salbutamol", "levothyroxine", "omeprazole", "atorvastatine", "bisoprolol",
    "ramipril", "furosemide", "metoprolol", "lisinopril", "enalapril",
    "captopril", "losartan", "valsartan", "irbesartan", "telmisartan",
    "simvastatine", "rosuvastatine", "fluvastatine", "pravastatine",
    "metronidazole", "amoxicilline clavulanate", "azithromycine", "doxycycline",
    "ciprofloxacine", "ofloxacine", "ceftriaxone", "cefixime", "cotrimoxazole",
    "isoniazide", "rifampicine", "ethambutol", "pyrazinamide",  # tuberculose (priorité Maroc)
    "chloroquine", "artemether", "sulfadoxine", "primaquine",    # paludisme
    "insuline", "glibenclamide", "glimepiride", "sitagliptine", "metformine",
    "prednisolone", "dexamethasone", "betamethasone", "hydrocortisone",
    "cetirizine", "loratadine", "desloratadine", "fexofenadine",
    "omeprazole", "lansoprazole", "esomeprazole", "pantoprazole", "ranitidine",
    "domperidone", "metoclopramide", "hyoscine", "phloroglucinol",
    "sertraline", "fluoxetine", "paroxetine", "escitalopram", "amitriptyline",
    "alprazolam", "diazepam", "bromazepam", "clonazepam", "zolpidem",
    "valproate", "carbamazepine", "phenytoine", "levetiracetam", "lamotrigine",
    "tramadol", "codeine", "morphine", "nefopam", "ketoprofene",
    "warfarine", "acenocoumarol", "clopidogrel", "aspirine", "heparine",
    "fer", "acide folique", "vitamine b12", "calcium", "vitamine d",
    "sels de rehydratation", "zinc", "albendazole", "mebendazole",  # OMS essentiels
    "amitriptyline", "nortriptyline", "clomipramine", "imipramine",
    "haloperidol", "chlorpromazine", "risperidone", "olanzapine",
    "cotrimoxazole", "dapsone", "streptomycine",
    "gentamicine", "amikacine", "tobramycine",
    "fluconazole", "amphotericine", "ketoconazole", "itraconazole",
    "aciclovir", "valaciclovir",
]


def fetch_moroccan_drugs(queries: list[str] = DRUG_QUERIES) -> list[dict]:
    """
    Fetch drug data from medicament.ma.

    Scrapes search results for each DCI query and extracts:
    - Nom commercial (Moroccan brand name)
    - Présentation
    - PPV (prix public de vente) in MAD
    - Prix hospitalier in MAD
    - Distributeur
    - Princeps/générique indicator
    """
    try:
        import httpx
        from html.parser import HTMLParser
    except ImportError:
        print("  [ERROR] pip install httpx")
        return []

    print(f"\n[medicament.ma] Fetching {len(queries)} drug queries...")

    class RowParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows = []
            self.current_row = []
            self.current_cell = ""
            self.in_td = False
            self.in_tr = False

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "tr":
                self.in_tr = True
                self.current_row = []
            elif tag == "td":
                self.in_td = True
                self.current_cell = ""

        def handle_endtag(self, tag):
            if tag == "td":
                self.current_row.append(self.current_cell.strip())
                self.in_td = False
            elif tag == "tr":
                if self.current_row and any(c.strip() for c in self.current_row):
                    self.rows.append(self.current_row[:])
                self.in_tr = False

        def handle_data(self, data):
            if self.in_td:
                self.current_cell += " " + data.strip()

    all_chunks = []
    seen_names = set()

    with httpx.Client(
        timeout=10.0,
        headers={"User-Agent": "MediSense-AI/1.0"},
        follow_redirects=True,
    ) as client:
        for i, query in enumerate(queries):
            try:
                resp = client.get(
                    MEDICAMENT_MA_BASE,
                    params={"page": "medicament", "action": "recherche", "quel": query},
                )
                resp.raise_for_status()
                html = resp.text

                parser = RowParser()
                parser.feed(html)

                count_added = 0
                for row in parser.rows:
                    if len(row) < 3:
                        continue
                    name = row[0].strip()
                    if not name or len(name) < 3:
                        continue
                    if name in seen_names or name.lower() in ("désignation", "nom", "medicament"):
                        continue
                    seen_names.add(name)

                    presentation = row[1].strip() if len(row) > 1 else ""
                    ppv = row[2].strip() if len(row) > 2 else ""
                    prix_hosp = row[3].strip() if len(row) > 3 else ""
                    distributeur = row[4].strip() if len(row) > 4 else ""
                    princeps = row[5].strip() if len(row) > 5 else ""

                    # Build rich text for RAG
                    text_parts = [f"{name}"]
                    if presentation:
                        text_parts.append(f"Présentation: {presentation}.")
                    if ppv:
                        text_parts.append(f"Prix public de vente (Maroc): {ppv} MAD.")
                    if prix_hosp:
                        text_parts.append(f"Prix hospitalier: {prix_hosp} MAD.")
                    if distributeur:
                        text_parts.append(f"Distributeur au Maroc: {distributeur}.")
                    if princeps:
                        text_parts.append(f"Statut: {princeps}.")
                    text_parts.append(f"Substance active recherchée: {query}.")

                    all_chunks.append({
                        "text": " ".join(text_parts),
                        "source": "dmp_maroc",
                        "type": "drug",
                        "name": name,
                        "icd10_codes": [],
                        "language": "fr",
                        "section": "fiche_medicament_maroc",
                        "country": "MA",
                        "currency": "MAD",
                        "ppv_dh": ppv,
                        "distributeur": distributeur,
                        "substance_active": query,
                    })
                    count_added += 1

                if (i + 1) % 10 == 0 or count_added > 0:
                    print(f"  [{i+1}/{len(queries)}] '{query}': +{count_added} → total {len(all_chunks)}")

                time.sleep(0.5)  # polite to the server

            except Exception as e:
                print(f"  [WARN] '{query}' failed: {e}")
                time.sleep(2)

    print(f"\n[medicament.ma] {len(all_chunks)} unique drug entries fetched")

    if not all_chunks:
        print("  [INFO] medicament.ma is JS-rendered — falling back to hardcoded drug monographies")
        all_chunks = _build_fallback_drug_chunks()

    return all_chunks


def _build_fallback_drug_chunks() -> list[dict]:
    """
    Fallback when medicament.ma is unavailable (JS-rendered, no API).
    Imports and returns the hardcoded drug monographies from build_corpus_local.py.
    These are medically accurate French-language monographies appropriate for Morocco.
    """
    try:
        from scripts.build_corpus_local import build_drug_chunks
        chunks = build_drug_chunks()
        print(f"  [fallback] {len(chunks)} drug chunks from hardcoded monographies")
        return chunks
    except ImportError:
        pass

    # If import fails (e.g. path issues), return minimal set
    print("  [WARN] Could not import build_corpus_local — drug data will be empty")
    return []


# ── 2. ICD-10 (universal, reused) ────────────────────────────────────────────

def build_icd10_chunks() -> list[dict]:
    try:
        import simple_icd_10 as icd
    except ImportError:
        print("  [ERROR] pip install simple-icd-10")
        return []

    print(f"\n[ICD-10] Building from simple-icd-10 package...")
    chunks = []
    for code in icd.get_all_codes():
        if icd.is_chapter_or_block(code):
            continue
        desc = icd.get_description(code)
        if not desc or len(desc) < 5:
            continue
        try:
            ancestors = icd.get_ancestors(code)
            context = " > ".join(
                icd.get_description(a)
                for a in ancestors
                if not icd.is_chapter_or_block(a)
            )[:2]
        except Exception:
            context = ""

        text = f"{desc} (ICD-10: {code})."
        if context:
            text += f" Catégorie: {context}."

        chunks.append({
            "text": text,
            "source": "icd10",
            "type": "disease",
            "name": desc,
            "icd10_codes": [code, code[:3]] if len(code) > 3 else [code],
            "language": "en",
            "section": "classification",
            "country": "INT",
        })

    print(f"  {len(chunks)} ICD-10 leaf chunks")
    return chunks


# ── 3. Morocco-specific clinical guidelines ──────────────────────────────────

# Based on Ministère de la Santé Maroc priority pathologies (Plan National de Santé)
# and SMSM protocoles thérapeutiques AMO
MOROCCAN_GUIDELINES = [
    ("Hypertension artérielle — Protocole thérapeutique Maroc (AMO)",
     "L'HTA touche 33% des adultes marocains > 45 ans. Objectif PA < 140/90 mmHg. "
     "Traitement de 1re ligne disponible au Maroc: IEC (captopril, lisinopril, ramipril), "
     "ARA2 (losartan, valsartan), inhibiteurs calciques (amlodipine, nifédipine), "
     "diurétiques (hydrochlorothiazide). Prise en charge dans le cadre de l'AMO/RAMED. "
     "Urgence hypertensive: appeler le 141 (SAMU Maroc) ou le 15."),

    ("Diabète de type 2 — Protocole AMO Maroc",
     "Le diabète affecte 10,6% de la population adulte marocaine (IDF 2021). "
     "Médicaments remboursés par l'AMO: metformine (1re intention), glibenclamide, "
     "glimepiride, insuline humaine NPH, insuline rapide. Objectif HbA1c < 7%. "
     "Surveillance: glycémie capillaire, HbA1c tous les 3 mois, fond d'œil annuel. "
     "Centres de diabétologie disponibles dans tous les CHU marocains."),

    ("Tuberculose — Guide national de prise en charge Maroc",
     "Le Maroc est pays à incidence intermédiaire (82/100 000). Programme National de Lutte "
     "contre la Tuberculose (PNLT). Traitement GRATUIT au Maroc (dispensaires antituberculeux). "
     "Schéma standard: 2RHZE/4RH (rifampicine, isoniazide, pyrazinamide, éthambutol). "
     "Durée: 6 mois minimum. Respect de l'observance OBLIGATOIRE (DOT — traitement directement observé). "
     "En cas de toux > 3 semaines: consultation obligatoire, crachat BK."),

    ("Urgences médicales au Maroc — Numéros et procédures",
     "Numéros d'urgence au Maroc: 141 = SAMU (urgences médicales), 150 = Pompiers/Secours, "
     "177 = Gendarmerie Royale, 19 = Police. "
     "SAMU disponible 24h/24 dans les grandes villes (Casablanca, Rabat, Marrakech, Fès, Agadir). "
     "Hôpitaux universitaires (CHU): Ibn Rochd (Casablanca), Ibn Sina (Rabat), "
     "Mohammed VI (Marrakech), Hassan II (Fès). "
     "Urgence cardiaque: appeler le 141 immédiatement."),

    ("Régime d'assurance maladie au Maroc — AMO/RAMED",
     "Assurance Maladie Obligatoire (AMO): pour salariés secteur public (CNOPS) et privé (CNSS). "
     "RAMED (Régime d'Assistance Médicale): pour population démunie, soins gratuits dans établissements publics. "
     "Médicaments remboursables: liste publiée par le Ministère de la Santé, prix plafonné (PPV). "
     "Taux de remboursement AMO: 70-90% selon médicament et spécialité. "
     "Pour connaître si un médicament est remboursé: consulter medicament.ma ou votre médecin traitant."),

    ("Paludisme — Prévention et traitement Maroc",
     "Le Maroc est officiellement certifié exempt de paludisme autochtone depuis 2010 (OMS). "
     "Risque uniquement pour voyageurs en zone d'endémie (Afrique subsaharienne, Asie). "
     "Prophylaxie pour voyageurs: chloroquine (zones résistance faible) ou "
     "atovaquone-proguanil/méfloquine (zones haute résistance). "
     "Symptômes à surveiller: fièvre, frissons, maux de tête au retour de voyage. "
     "Diagnostic: test de diagnostic rapide (TDR) disponible dans les hôpitaux marocains."),

    ("Santé maternelle et néonatale — Maroc",
     "Objectifs Plan Santé Maroc 2025: réduire mortalité maternelle à < 42/100 000. "
     "Consultations prénatales: au moins 4 visites recommandées (semaines 12, 20, 28, 36). "
     "Supplémentation systématique: acide folique 0,4mg/j avant conception et T1, "
     "fer 30-60mg/j T2-T3, calcium si carence. "
     "Accouchement: favoriser maternités publiques (gratuit sous RAMED). "
     "Allaitement maternel recommandé jusqu'à 6 mois exclusif, 2 ans total."),

    ("Vaccination — Programme National d'Immunisation Maroc (PNI)",
     "Vaccinations GRATUITES dans centres de santé publics marocains. "
     "Calendrier vaccinal Maroc 2024: BCG (naissance), Hépatite B (0-1-6 mois), "
     "Penta DTC-HiB-HépB (2-3-4 mois), Polio IPV, Pneumocoque PCV13, "
     "ROR (9 mois et 15-18 mois), Méningocoque (9 mois). "
     "Rappels: dTPolio adulte (tous les 10 ans). "
     "Grippe saisonnière: recommandée pour > 65 ans, femmes enceintes, patients chroniques."),

    ("Maladies cardiovasculaires — Contexte marocain",
     "Les maladies cardiovasculaires sont la 1re cause de mortalité au Maroc (34%). "
     "Facteurs de risque prioritaires au Maroc: HTA (33%), tabagisme, dyslipidémie, diabète, obésité. "
     "Statines disponibles et remboursées AMO: simvastatine, atorvastatine. "
     "Aspirine 75-100mg/j en prévention secondaire. "
     "Réhabilitation cardiaque: disponible dans CHU, insuffisante en zones rurales. "
     "IDM: appeler 141 immédiatement. Thrombolyse disponible dans CHU si pas de cathlab."),

    ("Santé mentale — Resources disponibles au Maroc",
     "Prévalence troubles mentaux au Maroc: 48,9% de la population a un trouble mental courant (OMS). "
     "Dépression: traitement de 1re ligne disponible AMO: antidépresseurs ISRS (fluoxétine, sertraline). "
     "Ligne d'écoute psychologique: disponible dans certaines villes. "
     "Structures spécialisées: CHU Ibn Rushd Casablanca (psychiatrie), CHU Rabat. "
     "Stigmatisation: principal obstacle au traitement au Maroc. "
     "Crise suicidaire: appeler le 141 ou se rendre aux urgences les plus proches."),

    ("Prescription et automédication — Contexte marocain",
     "Au Maroc, de nombreux médicaments vendus sans ordonnance en pratique. "
     "Risque majeur: antibiotiques (amoxicilline, cotrimoxazole) achetés sans prescription = résistances. "
     "Médicaments nécessitant ordonnance obligatoire: psychotropes (liste A et B), "
     "opioïdes (ordonnance sécurisée), anticancéreux. "
     "Prix des médicaments: PPV plafonné par l'État pour médicaments essentiels. "
     "Médicaments génériques: mêmes effets que princeps, prix réduit de 30-50%. "
     "Pharmacies de garde: consultez votre mairie ou l'application locale."),

    ("Cancer — Dépistage et accès aux soins au Maroc",
     "Plan National de Prévention et Contrôle du Cancer (PNPCC) 2020-2029. "
     "Cancers les plus fréquents au Maroc: sein (1re chez femme), poumon (1er chez homme), "
     "col utérin, colorectal, lymphome. "
     "Dépistage cancer du sein: mammographie gratuite dans centres de santé référents. "
     "Dépistage col utérin: frottis/IVA dans centres de santé. "
     "Centres oncologie: INO Rabat, CAC Casablanca, centres régionaux. "
     "Médicaments anticancéreux: remboursement AMO progressif selon liste nationale."),

    ("Nutrition et malnutrition — Maroc",
     "Double fardeau nutritionnel au Maroc: obésité (26,8% adultes) ET malnutrition en zones rurales. "
     "Carence en fer: fréquente chez femmes en âge de procréer et enfants < 5 ans. "
     "Supplémentation recommandée: fer chez femmes enceintes, vitamine D chez nourrissons. "
     "Allaitement maternel exclusif jusqu'à 6 mois. "
     "Régime méditerranéen/marocain traditionnel: protecteur si maintenu (huile d'argan, légumineuses). "
     "Obésité: facteur de risque HTA, diabète, cancer — prise en charge multidisciplinaire."),

    ("SIDA/VIH — Programme national Maroc",
     "Prévalence VIH au Maroc: 0,1% (épidémie concentrée). "
     "Traitement antirétroviral (ARV): GRATUIT au Maroc via Programme National (PNLS). "
     "Dépistage volontaire et confidentiel: centres de dépistage anonyme dans grandes villes. "
     "Prophylaxie pré-exposition (PrEP): disponible dans certains centres référents. "
     "ARV de 1re ligne disponibles: TDF+3TC+EFV (ligne fixe). "
     "PTME (prévention transmission mère-enfant): prise en charge intégrée en maternités."),

    ("Antibiothérapie responsable — Contexte marocain",
     "Résistance aux antibiotiques: problème majeur de santé publique au Maroc. "
     "JAMAIS d'antibiotiques pour: rhinopharyngite, grippe, bronchite virale (viral = pas d'antibiotiques). "
     "Prescription obligatoire recommandée (pas toujours respectée en pratique). "
     "Antibiotiques de référence au Maroc pour infections courantes: "
     "amoxicilline (angine TDR+), cotrimoxazole ou amoxicilline (IU simple), "
     "amoxicilline (pneumonie communautaire). "
     "Durée de traitement: respecter strictement la durée prescrite. "
     "Ne jamais partager ses antibiotiques ni conserver pour une prochaine fois."),
]


def build_moroccan_guidelines_chunks() -> list[dict]:
    chunks = []
    for title, content in MOROCCAN_GUIDELINES:
        chunks.append({
            "text": f"Guide clinique Maroc — {title}: {content}",
            "source": "ministere_sante_maroc",
            "type": "guideline",
            "name": title,
            "icd10_codes": [],
            "language": "fr",
            "section": "protocole_maroc",
            "country": "MA",
        })
        for i, sentence in enumerate([s.strip() for s in content.split(".") if len(s.strip()) > 40]):
            chunks.append({
                "text": f"{title} — {sentence}.",
                "source": "ministere_sante_maroc",
                "type": "guideline",
                "name": title,
                "icd10_codes": [],
                "language": "fr",
                "section": f"point_{i+1}",
                "country": "MA",
            })
    print(f"\n[Maroc Guidelines] {len(chunks)} chunks from {len(MOROCCAN_GUIDELINES)} guidelines")
    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid(text: str) -> str:
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def save(chunks: list[dict], filename: str) -> None:
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"  → Saved {len(chunks):,} chunks to {path.name}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-drugs", action="store_true", help="Skip medicament.ma fetching")
    parser.add_argument("--skip-icd10", action="store_true", help="Skip ICD-10 (already built)")
    args = parser.parse_args()

    print("=" * 60)
    print("MediSense — Moroccan Corpus Builder")
    print("=" * 60)

    if not args.skip_drugs:
        drugs = fetch_moroccan_drugs()
        save(drugs, "ansm_drugs.json")  # reuse same filename → ingest_from_files.py picks it up
    else:
        print("\n[SKIP] medicament.ma drugs")

    if not args.skip_icd10:
        icd10 = build_icd10_chunks()
        save(icd10, "icd10_full.json")
    else:
        print("\n[SKIP] ICD-10 (using existing file)")

    guidelines = build_moroccan_guidelines_chunks()
    save(guidelines, "has_guidelines.json")  # reuse filename → ingest_from_files.py picks it up

    print(f"\n{'='*60}")
    print("Corpus ready. Run:")
    print("  docker exec medisense_fastapi python scripts/ingest_from_files.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
