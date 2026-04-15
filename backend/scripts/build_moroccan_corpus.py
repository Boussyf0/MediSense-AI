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

MEDICAMENT_MA_LISTING = "https://medicament.ma/listing-des-medicaments/"

# All 26 letters — covers the full DMP registry (~5,000+ drugs)
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def fetch_moroccan_drugs(letters: list[str] = LETTERS, max_pages_per_letter: int = 50) -> list[dict]:
    """
    Fetch all drugs from medicament.ma using the letter-based listing pages.

    URL pattern: https://medicament.ma/listing-des-medicaments/?lettre=A
    Pagination:  https://medicament.ma/listing-des-medicaments/page/2/?lettre=A

    Each listing item provides:
      - Drug name + dosage + form (from <p class="primary">)
      - Presentation + PPV in dhs + Distributeur (from <span class="secondary">)
      - Individual drug page URL (for optional detail fetch)

    Returns one chunk per drug with PPV, distributeur, presentation.
    """
    try:
        import httpx
        import re
    except ImportError:
        print("  [ERROR] pip install httpx")
        return []

    print(f"\n[medicament.ma] Scraping letter-based listing (A-Z)...")

    _ITEM_RE = re.compile(
        r'<li class="listing-item">.*?<a href="([^"]+)"[^>]*>.*?'
        r'<p class="primary">([^<]+)</p>.*?'
        r'<span class="secondary">([^<]+)</span>',
        re.DOTALL,
    )
    _PAGE_RE = re.compile(r'/page/(\d+)/\?lettre=')
    _PPV_RE = re.compile(r'PPV:\s*([\d.,]+)\s*dhs', re.IGNORECASE)
    _DIST_RE = re.compile(r'-\s*([A-Z][^-]+)$')

    all_chunks = []
    seen_slugs: set[str] = set()

    with httpx.Client(
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; MediSense-AI/1.0; medical research)"},
        follow_redirects=True,
    ) as client:
        for letter in letters:
            letter_total = 0
            page = 1

            while page <= max_pages_per_letter:
                url = (
                    f"{MEDICAMENT_MA_LISTING}?lettre={letter}"
                    if page == 1
                    else f"{MEDICAMENT_MA_LISTING}page/{page}/?lettre={letter}"
                )
                try:
                    resp = client.get(url)
                    if resp.status_code == 404:
                        break  # no more pages
                    resp.raise_for_status()
                    html = resp.text

                    # Detect max pages for this letter (first page only)
                    if page == 1:
                        found_pages = _PAGE_RE.findall(html)
                        max_page = max((int(p) for p in found_pages), default=1)
                    else:
                        max_page = max_pages_per_letter  # already discovered

                    items = _ITEM_RE.findall(html)
                    if not items:
                        break  # empty page

                    for slug_url, primary, secondary in items:
                        slug = slug_url.rstrip("/").split("/")[-1]
                        if slug in seen_slugs:
                            continue
                        seen_slugs.add(slug)

                        name = primary.strip()
                        secondary = secondary.strip()

                        ppv_match = _PPV_RE.search(secondary)
                        ppv = ppv_match.group(1) if ppv_match else ""

                        # Presentation is everything before " - PPV"
                        presentation = secondary.split(" - PPV:")[0].strip() if " - PPV:" in secondary else secondary

                        # Distributeur is last segment after last " - "
                        dist_match = _DIST_RE.search(secondary)
                        distributeur = dist_match.group(1).strip() if dist_match else ""

                        # Build RAG-friendly text
                        parts = [f"Médicament marocain: {name}."]
                        if presentation:
                            parts.append(f"Présentation: {presentation}.")
                        if ppv:
                            parts.append(f"Prix public de vente au Maroc (PPV): {ppv} dhs (MAD).")
                        if distributeur:
                            parts.append(f"Distributeur/fabricant au Maroc: {distributeur}.")
                        parts.append("Source: DMP — Direction du Médicament et de la Pharmacie, Maroc.")

                        all_chunks.append({
                            "text": " ".join(parts),
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
                            "slug": slug,
                        })
                        letter_total += 1

                    if page >= max_page:
                        break
                    page += 1
                    time.sleep(1.0)  # polite — 1 req/sec

                except Exception as e:
                    print(f"  [WARN] {letter} p{page}: {e}")
                    time.sleep(3)
                    break

            print(f"  [{letter}] {letter_total} drugs (total: {len(all_chunks)})")

    print(f"\n[medicament.ma] {len(all_chunks)} unique drugs fetched from DMP registry")

    if not all_chunks:
        print("  [INFO] No data fetched — falling back to hardcoded drug monographies")
        all_chunks = _build_fallback_drug_chunks()

    return all_chunks


def enrich_drug_details(chunks: list[dict], sample_size: int = 500) -> list[dict]:
    """
    Enrich drug chunks with detail page data: Composition (DCI), Classe thérapeutique,
    Code ATC, Générique/Princeps status.

    Fetches individual drug pages. Limited to `sample_size` to keep runtime reasonable.
    (~500 drugs × 1.5s = ~12 min)
    """
    try:
        import httpx
        import re
    except ImportError:
        return chunks

    # Prioritise drugs that have a slug (all from listing scraper)
    to_enrich = [c for c in chunks if c.get("slug")][:sample_size]
    if not to_enrich:
        return chunks

    print(f"\n[detail pages] Enriching {len(to_enrich)} drug pages with DCI/ATC/classe thérapeutique...")

    _DETAIL_RE = re.compile(
        r'<div class="detail-header">([^<]+)</div>\s*<div class="detail-content">(.*?)</div>',
        re.DOTALL,
    )
    _TAG_RE = re.compile(r'<[^>]+>')
    _STATUS_RE = re.compile(r'<span class="tag">([^<]+)</span>')

    slug_to_detail: dict[str, dict] = {}

    with httpx.Client(
        timeout=15.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; MediSense-AI/1.0)"},
        follow_redirects=True,
    ) as client:
        for i, chunk in enumerate(to_enrich):
            slug = chunk["slug"]
            url = f"https://medicament.ma/medicament/{slug}/"
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    continue
                html = resp.text

                detail: dict[str, str] = {}
                for header, content in _DETAIL_RE.findall(html):
                    key = header.strip().lower()
                    val = _TAG_RE.sub("", content).strip()
                    detail[key] = val

                # Générique / Princeps tag
                tag_match = _STATUS_RE.search(html)
                if tag_match:
                    detail["statut_commercial"] = tag_match.group(1).strip()

                slug_to_detail[slug] = detail

                if (i + 1) % 50 == 0:
                    print(f"  [{i+1}/{len(to_enrich)}] enriched {len(slug_to_detail)} drugs")

                time.sleep(1.2)

            except Exception:
                time.sleep(2)

    # Merge details back into chunks
    enriched = 0
    for chunk in chunks:
        slug = chunk.get("slug", "")
        detail = slug_to_detail.get(slug)
        if not detail:
            continue

        composition = detail.get("composition", "")
        classe = detail.get("classe thérapeutique", "")
        atc = detail.get("code atc", "")
        statut = detail.get("statut_commercial", "")

        extras = []
        if composition:
            extras.append(f"Composition (DCI): {composition}.")
        if classe:
            extras.append(f"Classe thérapeutique: {classe}.")
        if atc:
            extras.append(f"Code ATC: {atc}.")
        if statut:
            extras.append(f"Statut: {statut}.")

        if extras:
            chunk["text"] += " " + " ".join(extras)
            chunk["composition"] = composition
            chunk["atc"] = atc
            chunk["classe_therapeutique"] = classe
            enriched += 1

    print(f"  → {enriched} drugs enriched with DCI/ATC/classe thérapeutique")
    return chunks


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
    parser.add_argument("--fetch-details", action="store_true",
                        help="Enrich drugs with detail pages (DCI/ATC/classe). Adds ~12 min.")
    parser.add_argument("--detail-sample", type=int, default=500,
                        help="Max drugs to enrich with detail pages (default: 500)")
    args = parser.parse_args()

    print("=" * 60)
    print("MediSense — Moroccan Corpus Builder")
    print("=" * 60)

    if not args.skip_drugs:
        drugs = fetch_moroccan_drugs()
        if args.fetch_details and drugs:
            drugs = enrich_drug_details(drugs, sample_size=args.detail_sample)
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
