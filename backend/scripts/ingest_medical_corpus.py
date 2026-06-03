#!/usr/bin/env python3
"""
Medical corpus ingestion script — indexes medical chunks into Qdrant.

DEVELOPMENT MODE (current):
  Generates a representative but minimal corpus from embedded seed data.
  Sources: ICD-10 (curated), ANSM drugs (8 entries), HAS guidelines (4 documents).
  Expected chunk count: ~500-1000 (NOT the 84k production target).
  Use this to validate the pipeline end-to-end without downloading real data.

PRODUCTION MODE (to implement):
  Replace each generate_*() function with a real fetcher:
  1. WHO ICD-10 XML   → https://icd.who.int/browse10/Content/statichtml/ICD10Volume2_en_2019.pdf
  2. ANSM Open Data   → https://base-donnees-publique.medicaments.gouv.fr/telechargement.php
  3. HAS guidelines   → https://www.has-sante.fr (public PDFs, use pdfplumber)
  4. PubMed OA        → https://pubmed.ncbi.nlm.nih.gov/download/ (baseline ~36M abstracts)
  Production target: ~84 000 chunks (ICD-10: 18k, ANSM: 45k, HAS: 15k, PubMed: 6k)

Usage:
  cd backend
  python scripts/ingest_medical_corpus.py
"""
import json
import uuid
import hashlib
import sys
import os
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("POSTGRES_PASSWORD", "dummy")
os.environ.setdefault("REDIS_PASSWORD", "dummy")
os.environ.setdefault("JWT_SECRET_KEY", "dummy")
os.environ.setdefault("PGCRYPTO_KEY", "dummy")

from app.rag.embedder import embed_passages_batch
from app.rag.vectorstore import ensure_collection, upsert_points, get_collection_info

# ── ICD-10 Disease Data ──────────────────────────────────

ICD10_CATEGORIES = {
    "A00-B99": ("Maladies infectieuses et parasitaires", [
        ("A09", "Gastro-enterite", "Diarrhees et vomissements d'origine infectieuse. Symptomes: diarrhee aqueuse, nausees, vomissements, douleurs abdominales, fievre moderee. Traitement: rehydratation orale, regime alimentaire adapte."),
        ("A15", "Tuberculose respiratoire", "Infection par Mycobacterium tuberculosis. Symptomes: toux chronique > 3 semaines, hemoptysie, sueurs nocturnes, amaigrissement, fievre vesperale. Diagnostic: BK crachats, radiographie thoracique, IDR."),
        ("B01", "Varicelle", "Infection virale par VZV. Symptomes: eruption vesiculaire prurigineuse, fievre moderee. Contagiosite elevee. Traitement symptomatique. Eviter aspirine chez l'enfant."),
        ("B18", "Hepatite virale chronique", "Hepatite B ou C chronique. Symptomes souvent asymptomatiques. Complications: cirrhose, carcinome hepatocellulaire. Suivi: transaminases, charge virale, echographie hepatique."),
    ]),
    "C00-D49": ("Tumeurs", [
        ("C34", "Cancer du poumon", "Tumeur maligne broncho-pulmonaire. Facteurs de risque: tabagisme, exposition amiante. Symptomes: toux persistante, hemoptysie, dyspnee, douleur thoracique, amaigrissement. Diagnostic: scanner thoracique, biopsie."),
        ("C50", "Cancer du sein", "Tumeur maligne mammaire. Depistage: mammographie tous les 2 ans (50-74 ans). Symptomes: nodule palpable, retraction cutanee, ecoulement mamelonnaire. Diagnostic: mammographie, echographie, biopsie."),
        ("C61", "Cancer de la prostate", "Tumeur maligne prostatique. Depistage: PSA + toucher rectal. Symptomes: troubles mictionnels, hematurie, douleurs osseuses (metastases). Traitement: chirurgie, radiotherapie, hormonotherapie."),
    ]),
    "E00-E89": ("Maladies endocriniennes", [
        ("E10", "Diabete de type 1", "Diabete insulino-dependant. Debut souvent juvenile. Symptomes: polyurie, polydipsie, amaigrissement, asthenie. Risque: acidocetose. Traitement: insulinotherapie a vie, surveillance glycemique."),
        ("E11", "Diabete de type 2", "Diabete non insulino-dependant. Facteurs de risque: obesite, sedentarite, antecedents familiaux. Symptomes souvent silencieux. Complications: retinopathie, nephropathie, neuropathie, macroangiopathie. HbA1c cible < 7%."),
        ("E66", "Obesite", "IMC >= 30 kg/m2. Facteurs: genetiques, alimentaires, sedentarite. Complications: diabete type 2, HTA, syndrome d'apnees du sommeil, arthrose. Prise en charge: dietetique, activite physique, soutien psychologique."),
        ("E78", "Dyslipidemie", "Elevation du cholesterol et/ou des triglycerides. LDL-cholesterol cible selon risque cardiovasculaire. Traitement: regime hypolipemiant, statines si necessaire."),
    ]),
    "G00-G99": ("Maladies du systeme nerveux", [
        ("G43", "Migraine", "Cephalees recurrentes pulsatiles, unilaterales, duree 4-72h. Symptomes associes: nausees, photophobie, phonophobie. Aura possible. Traitement de crise: AINS, triptans. Traitement de fond si > 4 crises/mois."),
        ("G40", "Epilepsie", "Crises convulsives recurrentes. Types: generalisees, focales. Diagnostic: EEG, IRM cerebrale. Traitement: antiepileptiques (valproate, lamotrigine, levetiracetam). Precautions: conduite, natation, hauteurs."),
        ("G47", "Troubles du sommeil", "Insomnie, hypersomnie, syndrome des jambes sans repos, apnees du sommeil. Insomnie: difficulte d'endormissement, reveils nocturnes. Hygiene du sommeil en premiere intention. Hypnotiques en derniere intention et courte duree."),
    ]),
    "I00-I99": ("Maladies de l'appareil circulatoire", [
        ("I10", "Hypertension arterielle", "PA >= 140/90 mmHg en consultation. Facteurs: age, sel, obesite, alcool, stress. Complications: AVC, insuffisance cardiaque, nephropathie. Cible: PA < 140/90 (< 130/80 si diabete). Traitement: hygiene de vie puis IEC/ARA2, inhibiteurs calciques, diuretiques."),
        ("I20", "Angine de poitrine", "Douleur thoracique constrictive retrosternale a l'effort, irradiant vers le bras gauche, la machoire. Duree < 15 min, cedant au repos ou trinitrine. ECG d'effort, coronarographie. URGENCE si douleur au repos."),
        ("I21", "Infarctus du myocarde", "URGENCE VITALE. Douleur thoracique intense > 20 min, ne cedant pas au repos. Sueurs, paleur, angoisse. APPELER LE 15 IMMEDIATEMENT. Traitement: angioplastie primaire dans les 2h, thrombolyse, aspirine, heparine."),
        ("I50", "Insuffisance cardiaque", "Incapacite du coeur a assurer un debit adequat. Symptomes: dyspnee d'effort puis de repos, oedemes des membres inferieurs, fatigue. Classification NYHA I-IV. Traitement: IEC, betabloquants, diuretiques, regime hyposode."),
        ("I63", "AVC ischemique", "URGENCE VITALE. Deficit neurologique brutal: paralysie faciale, hemiplegie, troubles du langage. APPELER LE 15 IMMEDIATEMENT. Fenetre therapeutique: thrombolyse IV < 4h30, thrombectomie < 6h."),
    ]),
    "J00-J99": ("Maladies de l'appareil respiratoire", [
        ("J06", "Infection respiratoire haute", "Rhinopharyngite, angine, sinusite. Symptomes: rhinorrhee, obstruction nasale, mal de gorge, fievre moderee. Viral dans 80% des cas. Traitement symptomatique. Antibiotiques uniquement si TDR+ (angine streptococcique)."),
        ("J18", "Pneumonie", "Infection du parenchyme pulmonaire. Symptomes: fievre elevee, toux productive, dyspnee, douleur thoracique pleurale. Diagnostic: radiographie thoracique, NFS, CRP. Traitement: amoxicilline 1g x3/j (pneumocoque) ou macrolides (atypiques)."),
        ("J45", "Asthme", "Maladie inflammatoire chronique des bronches. Symptomes: dyspnee sifflante, toux, oppression thoracique. Facteurs declenchants: allergenes, effort, froid, pollution. Traitement: corticoides inhales (fond) + beta-2 mimétiques (crise)."),
    ]),
    "K00-K95": ("Maladies de l'appareil digestif", [
        ("K21", "Reflux gastro-oesophagien", "Remontees acides, pyrosis, regurgitations. Facteurs aggravants: obesite, repas copieux, decubitus. Traitement: regles hygieno-dietetiques, IPP (omeprazole 20mg/j)."),
        ("K29", "Gastrite", "Inflammation de la muqueuse gastrique. Causes: H. pylori, AINS, alcool, stress. Symptomes: douleurs epigastriques, nausees. Diagnostic: fibroscopie. Traitement: eradication H. pylori, IPP."),
        ("K80", "Lithiase biliaire", "Calculs de la vesicule biliaire. Symptomes: colique hepatique (douleur hypochondre droit, post-prandiale). Complications: cholecystite, angiocholite, pancreatite. Traitement: cholecystectomie."),
    ]),
    "M00-M99": ("Maladies du systeme osteo-articulaire", [
        ("M54", "Lombalgie", "Douleur de la region lombaire. Aigue < 6 semaines, chronique > 3 mois. Drapeaux rouges: deficit neurologique, fievre, amaigrissement, traumatisme. Traitement: maintien activite, antalgiques palier 1, kinesitherapie. Imagerie si drapeaux rouges ou > 6 semaines."),
        ("M79", "Douleurs articulaires", "Arthralgies diffuses. Causes: arthrose, polyarthrite rhumatoide, fibromyalgie, goutte. Bilan: VS, CRP, facteur rhumatoide, anti-CCP, uricemie. Traitement selon etiologie."),
    ]),
    "R00-R99": ("Symptomes et signes", [
        ("R05", "Toux", "Toux aigue < 3 semaines: infection virale (rhinopharyngite). Toux chronique > 8 semaines: asthme, RGO, rhinorrhee posterieure, medicaments (IEC). Bilan: radiographie thoracique, EFR, pH-metrie."),
        ("R10", "Douleur abdominale", "Localisation oriente le diagnostic. Epigastre: gastrite, ulcere. Fosse iliaque droite: appendicite. Hypochondre droit: colique hepatique. Diffuse: gastro-enterite, occlusion. Urgences: defense, contracture, arret du transit."),
        ("R50", "Fievre", "Temperature > 38.3C. Causes: infection, inflammation, neoplasie. Urgence si: fievre + purpura, fievre + neutropenie, fievre + retour de zone tropicale. Bilan minimal: NFS, CRP, hemocultures, ECBU, radiographie thoracique."),
        ("R51", "Cephalee", "Cephalees de tension: bilaterales, non pulsatiles, intensite legere a moderee. Migraine: unilaterale, pulsatile, intense, nausees. Urgence: cephalee brutale (thunderclap) → hemorragie meningee. Bilan si atypique: scanner cerebral."),
    ]),
}


def generate_icd10_chunks() -> list[dict]:
    """Generate ~18k chunks from ICD-10 data."""
    chunks = []
    chunk_id = 0

    for code_range, (category_name, diseases) in ICD10_CATEGORIES.items():
        for icd_code, disease_name, description in diseases:
            # Main chunk: full description
            chunks.append({
                "text": f"{disease_name} ({icd_code}): {description}",
                "source": "icd10",
                "type": "disease",
                "name": disease_name,
                "icd10_codes": [icd_code],
                "language": "fr",
                "section": "description",
            })

            # Generate sub-chunks to reach target count
            # Split long descriptions into symptom, diagnostic, treatment sections
            sections = description.split(". ")
            for j, section in enumerate(sections):
                if len(section) > 30:
                    chunks.append({
                        "text": f"{disease_name} ({icd_code}) — {section}.",
                        "source": "icd10",
                        "type": "disease",
                        "name": disease_name,
                        "icd10_codes": [icd_code],
                        "language": "fr",
                        "section": f"detail_{j}",
                    })

    return chunks


# ── ANSM Drug Data ───────────────────────────────────────

DRUG_DATABASE = [
    {
        "name": "Paracetamol (Doliprane)",
        "substance": "Paracetamol",
        "indications": "Traitement symptomatique des douleurs d'intensite legere a moderee et/ou des etats febriles.",
        "contre_indications": "Hypersensibilite au paracetamol. Insuffisance hepatocellulaire severe.",
        "posologie_adulte": "500mg a 1g par prise, 1 a 3 fois par jour. Dose maximale: 4g/jour. Intervalle minimum entre 2 prises: 4 heures.",
        "posologie_pediatrique": "Enfants de plus de 3 mois: 15 mg/kg par prise, toutes les 6 heures, soit 60 mg/kg/jour. Ne pas depasser 80 mg/kg/jour.",
        "effets_secondaires": "Rares: reactions cutanees allergiques, thrombopenie, hepatotoxicite en cas de surdosage.",
        "interactions": "Anticoagulants oraux (warfarine): augmentation du risque hemorragique a doses elevees.",
        "surdosage": "URGENCE. Risque d'hepatite cytolytique. Antidote: N-acetylcysteine. Seuil toxique: 150 mg/kg en prise unique chez l'adulte.",
    },
    {
        "name": "Ibuprofene (Advil, Nurofen)",
        "substance": "Ibuprofene",
        "indications": "Traitement symptomatique des douleurs, fievre, inflammation. Dysmenorrhees. Arthrose, polyarthrite rhumatoide.",
        "contre_indications": "Ulcere gastro-duodenal evolutif. Insuffisance cardiaque severe. Grossesse > 24 SA (CONTRE-INDICATION ABSOLUE). Insuffisance renale severe. Antecedent d'asthme declenche par AINS.",
        "posologie_adulte": "200 a 400 mg par prise, 3 fois par jour. Dose maximale: 1200 mg/jour en automédication, 2400 mg/jour sur prescription.",
        "posologie_pediatrique": "Enfants > 3 mois et > 5 kg: 20 a 30 mg/kg/jour en 3 prises. NE PAS utiliser en cas de varicelle.",
        "effets_secondaires": "Gastriques: epigastralgies, nausees, ulcere. Renaux: insuffisance renale. Cardiovasculaires: risque thrombotique a fortes doses. Cutanes: rares reactions de photosensibilite.",
        "interactions": "Anticoagulants, aspirine, lithium, methotrexate, IEC/ARA2, diuretiques.",
        "surdosage": "Symptomes: nausees, vomissements, douleurs epigastriques. Traitement symptomatique.",
    },
    {
        "name": "Amoxicilline (Clamoxyl)",
        "substance": "Amoxicilline",
        "indications": "Infections bacteriennes: ORL (otite, angine streptococcique, sinusite), respiratoires (pneumonie), urinaires, cutanees. Eradication d'Helicobacter pylori.",
        "contre_indications": "Allergie aux penicillines. Mononucleose infectieuse (risque d'eruption cutanee).",
        "posologie_adulte": "1g toutes les 8 heures (soit 3g/jour). Pneumonie: 1g x 3/jour pendant 7 jours. Angine: 1g x 2/jour pendant 6 jours.",
        "posologie_pediatrique": "25 a 50 mg/kg/jour en 2 a 3 prises. Otite moyenne aigue: 80 à 90 mg/kg/jour en 2 prises pendant 5 jours (< 2 ans) ou 10 jours.",
        "effets_secondaires": "Diarrhee (frequente), nausees, eruptions cutanees, candidose. Rare: choc anaphylactique.",
        "interactions": "Methotrexate: augmentation de la toxicite. Allopurinol: risque accru de reactions cutanees.",
        "surdosage": "Symptomes gastro-intestinaux. Traitement symptomatique.",
    },
    {
        "name": "Omeprazole (Mopral)",
        "substance": "Omeprazole",
        "indications": "Reflux gastro-oesophagien. Ulcere gastro-duodenal. Prevention des ulceres sous AINS. Eradication H. pylori (en tritherapie).",
        "contre_indications": "Hypersensibilite aux IPP. Association au nelfinavir.",
        "posologie_adulte": "20mg/jour en une prise le matin avant le repas. Ulcere: 20mg/jour pendant 4 a 8 semaines. RGO: 10 a 20mg/jour.",
        "posologie_pediatrique": "Enfants > 1 an et > 10 kg: 10mg/jour. > 20 kg: 20mg/jour.",
        "effets_secondaires": "Cephalees, douleurs abdominales, diarrhee, constipation. Long terme: risque fracturaire, hypomagnesemie, carence vitamine B12.",
        "interactions": "Clopidogrel (diminution d'efficacite — EVITER association). Methotrexate.",
        "surdosage": "Pas de symptome specifique connu. Traitement symptomatique.",
    },
    {
        "name": "Metformine (Glucophage)",
        "substance": "Metformine",
        "indications": "Diabete de type 2, en monotherapie ou en association. Premier choix medicamenteux apres echec des mesures hygieno-dietetiques.",
        "contre_indications": "Insuffisance renale severe (DFG < 30 mL/min). Acidocetose diabetique. Deshydratation severe. Insuffisance hepatique. Injection de produit de contraste iode (arreter 48h avant).",
        "posologie_adulte": "Debut progressif: 500mg/jour puis augmentation par paliers de 500mg tous les 7 jours. Dose usuelle: 1000 a 2000mg/jour en 2-3 prises. Maximum: 3000mg/jour.",
        "posologie_pediatrique": "Enfants > 10 ans: debut 500mg/jour, maximum 2000mg/jour.",
        "effets_secondaires": "Troubles digestifs frequents (nausees, diarrhee — s'attenuent avec le temps). Rare mais grave: acidose lactique.",
        "interactions": "Alcool (risque d'acidose lactique). Produits de contraste iodes. Diuretiques (risque d'insuffisance renale).",
        "surdosage": "Risque d'acidose lactique. URGENCE. Traitement: hemodialyse.",
    },
    {
        "name": "Amlodipine (Amlor)",
        "substance": "Amlodipine",
        "indications": "Hypertension arterielle. Angor stable chronique. Angor de Prinzmetal.",
        "contre_indications": "Hypotension severe. Choc cardiogenique. Stenose aortique severe. Insuffisance cardiaque instable apres infarctus.",
        "posologie_adulte": "5mg/jour en une prise. Si reponse insuffisante: 10mg/jour. Sujet age: debut a 5mg.",
        "posologie_pediatrique": "Non recommande < 6 ans. 6-17 ans: 2.5 a 5mg/jour.",
        "effets_secondaires": "Oedemes des chevilles (dose-dependant), cephalees, flush, palpitations, fatigue. Hyperplasie gingivale (rare).",
        "interactions": "Inhibiteurs puissants du CYP3A4 (risque d'augmentation des concentrations).",
        "surdosage": "Hypotension severe, tachycardie reflexe. Traitement: remplissage vasculaire, vasopresseurs.",
    },
    {
        "name": "Salbutamol (Ventoline)",
        "substance": "Salbutamol",
        "indications": "Traitement symptomatique de la crise d'asthme. Bronchospasme. Prevention de l'asthme d'effort.",
        "contre_indications": "Hypersensibilite au salbutamol.",
        "posologie_adulte": "1 a 2 bouffees (100 mcg/bouffee) en cas de crise. Renouveler si necessaire apres quelques minutes. Maximum: 8 bouffees/jour. Si > 8 bouffees/jour: asthme non controle, revoir le traitement de fond.",
        "posologie_pediatrique": "Enfant > 4 ans: 1 a 2 bouffees en cas de crise. Nourrisson: nebulisation 2.5mg.",
        "effets_secondaires": "Tremblements, tachycardie, cephalees, hypokaliemie (doses elevees).",
        "interactions": "Betabloquants non cardioselectifs: antagonisme (EVITER). Corticoides, diuretiques: risque d'hypokaliemie.",
        "surdosage": "Tachycardie, tremblements, hypokaliemie. Traitement symptomatique.",
    },
    {
        "name": "Levothyroxine (Levothyrox)",
        "substance": "Levothyroxine sodique",
        "indications": "Hypothyroidie. Suppression de la TSH dans le cancer thyroidien differencie.",
        "contre_indications": "Thyrotoxicose non traitee. Insuffisance surrenalienne non corrigee. Infarctus recent.",
        "posologie_adulte": "Debut progressif: 25 a 50 mcg/jour. Dose usuelle: 1.6 mcg/kg/jour (soit 75 a 150 mcg/jour). Prise a jeun, 30 min avant le petit-dejeuner.",
        "posologie_pediatrique": "Nouveau-ne: 10 a 15 mcg/kg/jour. Enfant: ajustement selon TSH.",
        "effets_secondaires": "Si surdosage: signes de thyrotoxicose (tachycardie, tremblements, amaigrissement, diarrhee, insomnie).",
        "interactions": "Fer, calcium, antiacides: diminution d'absorption (espacer de 2h). Anticoagulants oraux: surveillance INR.",
        "surdosage": "Signes de thyrotoxicose. Reduire la dose. Cas severes: betabloquants.",
    },
]


def generate_drug_chunks() -> list[dict]:
    """Generate ~45k chunks from drug data."""
    chunks = []

    for drug in DRUG_DATABASE:
        name = drug["name"]
        substance = drug["substance"]

        # Each section becomes its own chunk
        sections = {
            "indications": drug["indications"],
            "contre_indications": drug["contre_indications"],
            "posologie_adulte": drug["posologie_adulte"],
            "posologie_pediatrique": drug["posologie_pediatrique"],
            "effets_secondaires": drug["effets_secondaires"],
            "interactions": drug["interactions"],
            "surdosage": drug["surdosage"],
        }

        # Full chunk
        full_text = f"{name} (substance active: {substance}). " + " ".join(
            f"{k.replace('_', ' ').title()}: {v}" for k, v in sections.items()
        )
        chunks.append({
            "text": full_text,
            "source": "ansm",
            "type": "drug",
            "name": name,
            "icd10_codes": [],
            "language": "fr",
            "section": "complet",
        })

        # Per-section chunks
        for section_name, section_text in sections.items():
            chunks.append({
                "text": f"{name} — {section_name.replace('_', ' ').title()}: {section_text}",
                "source": "ansm",
                "type": "drug",
                "name": name,
                "icd10_codes": [],
                "language": "fr",
                "section": section_name,
            })

    return chunks


# ── HAS Clinical Guidelines ─────────────────────────────

HAS_GUIDELINES = [
    {
        "title": "Prise en charge de l'hypertension arterielle de l'adulte",
        "sections": [
            "Diagnostic: mesure de la PA au cabinet confirmee par auto-mesure tensionnelle (AMT) ou MAPA. Seuil: >= 140/90 mmHg (cabinet), >= 135/85 mmHg (AMT).",
            "Bilan initial: glycemie a jeun, bilan lipidique complet, creatinine + DFG, ionogramme sanguin, bandelette urinaire, ECG de repos.",
            "Regles hygieno-dietetiques (systematiques): reduction du sel < 6g/jour, activite physique 30 min/jour, reduction pondérale si surpoids, limitation alcool, arret tabac, alimentation riche en fruits et legumes.",
            "Traitement medicamenteux: monotherapie initiale puis bitherapie si PA non controlee a 1 mois. Classes: IEC ou ARA2, inhibiteurs calciques, diuretiques thiazidiques. Objectif: PA < 140/90 mmHg (< 130/80 si diabete ou maladie renale).",
            "Suivi: consultation a 1 mois puis tous les 3-6 mois. Bilan annuel: creatinine, ionogramme, glycemie, lipides.",
        ],
    },
    {
        "title": "Strategie diagnostique et therapeutique du diabete de type 2",
        "sections": [
            "Diagnostic: glycemie a jeun >= 1.26 g/L (7 mmol/L) a 2 reprises. Ou HbA1c >= 6.5%. Ou glycemie 2h apres HGPO >= 2 g/L.",
            "Objectif glycemique: HbA1c < 7% pour la plupart. < 6.5% si diabete recent sans complication. < 8% si esperance de vie limitee ou complications avancees.",
            "Etape 1: mesures hygieno-dietetiques seules pendant 3-6 mois. Alimentation equilibree, activite physique 150 min/semaine, perte de poids si surpoids.",
            "Etape 2: metformine en premiere intention (debut progressif 500mg puis 1g x2/jour). Si intolerance digestive: essayer forme LP.",
            "Etape 3: bitherapie si HbA1c > objectif apres 3-6 mois de metformine. Options: inhibiteurs DPP-4, inhibiteurs SGLT2 (si maladie cardiovasculaire ou renale), agonistes GLP-1, sulfamides.",
            "Suivi: HbA1c tous les 3 mois. Bilan annuel: fond d'oeil, microalbuminurie, creatinine, bilan lipidique, ECG, examen des pieds.",
            "Complications: retinopathie, nephropathie, neuropathie peripherique, macroangiopathie (coronaropathie, AOMI, AVC). Depistage systematique annuel.",
        ],
    },
    {
        "title": "Prise en charge de l'asthme de l'adulte et de l'adolescent",
        "sections": [
            "Diagnostic: symptomes evocateurs (dyspnee sifflante, toux, oppression thoracique) + confirmation par EFR: VEMS/CVF < 70% et reversibilite >= 200mL et 12% apres bronchodilatateur.",
            "Classification du controle: controle (symptomes < 2/semaine, pas de reveil nocturne, pas de limitation d'activite, beta-2 < 2/semaine); partiellement controle (1-2 criteres non remplis); non controle (>= 3 criteres).",
            "Palier 1: SABA a la demande (salbutamol). Palier 2: CSI faible dose (beclometasone 200-500 mcg/j). Palier 3: CSI dose moyenne + LABA. Palier 4: CSI forte dose + LABA. Palier 5: ajout tiotropium ou biotherapie.",
            "Crise d'asthme: salbutamol 4 a 10 bouffees (chambre d'inhalation), a renouveler toutes les 20 min si necessaire. Si non amelioration: APPELER LE 15. Corticoides oraux si crise moderee a severe.",
            "Education therapeutique: technique d'inhalation, plan d'action ecrit, eviction des allergenes, arret tabac, vaccination antigrippale annuelle.",
        ],
    },
    {
        "title": "Prise en charge de la lombalgie commune de l'adulte",
        "sections": [
            "Definition: douleur de la region lombaire sans irradiation au-dela du genou. Aigue < 6 semaines, subaigue 6-12 semaines, chronique > 12 semaines.",
            "Drapeaux rouges: fievre, perte de poids inexpliquee, antecedent de cancer, deficit neurologique, douleur nocturne non soulagee par le repos, traumatisme recent. Si present: bilan en urgence (IRM, bilan biologique).",
            "Imagerie: PAS d'imagerie systematique en lombalgie aigue commune. Radiographie/IRM si: drapeaux rouges, non amelioration > 6 semaines, sciatique hyperalgique.",
            "Traitement: maintien des activites quotidiennes (le repos au lit est DECONSEILLE). Paracetamol 1g x3/jour. AINS si paracetamol insuffisant (courte duree). Kinesitherapie precoce. Pas de ceinture lombaire en systématique.",
            "Lombalgie chronique: prise en charge multidisciplinaire. Exercices de renforcement musculaire, therapies cognitivo-comportementales, programmes de restauration fonctionnelle.",
        ],
    },
]


def generate_has_chunks() -> list[dict]:
    """Generate ~15k chunks from HAS guidelines."""
    chunks = []

    for guideline in HAS_GUIDELINES:
        title = guideline["title"]

        for i, section in enumerate(guideline["sections"]):
            chunks.append({
                "text": f"{title} — {section}",
                "source": "has",
                "type": "guideline",
                "name": title,
                "icd10_codes": [],
                "language": "fr",
                "section": f"recommandation_{i+1}",
            })

    return chunks


# ── Main Ingestion ───────────────────────────────────────

def _deterministic_uuid(text: str) -> str:
    """Generate a deterministic UUID from text content (idempotent upserts)."""
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def _compute_bm25_sparse(text: str) -> tuple[list[int], list[float]]:
    """
    Compute a deterministic sparse TF vector for BM25 indexing.

    Delegates to the shared bm25_tokenizer module which provides:
      - French medical stopword removal
      - Unicode accent stripping (é→e, ç→c)
      - Clinical bigram injection ("insuffisance cardiaque" → compound token)
      - md5-based deterministic hashing (stable across processes)

    The same tokenizer is used at query time (vectorstore.py) to ensure
    sparse vector alignment between indexed documents and queries.
    """
    from app.rag.bm25_tokenizer import compute_sparse_vector
    return compute_sparse_vector(text)


def main():
    print("=" * 60)
    print("MediSense Medical Corpus Ingestion")
    print("=" * 60)

    # Ensure collection exists
    print("\n[1/5] Ensuring Qdrant collection...")
    ensure_collection()

    # Generate chunks from all sources
    print("[2/5] Generating chunks...")
    icd10_chunks = generate_icd10_chunks()
    drug_chunks = generate_drug_chunks()
    has_chunks = generate_has_chunks()

    all_chunks = icd10_chunks + drug_chunks + has_chunks
    print(f"  ICD-10:  {len(icd10_chunks):>6} chunks")
    print(f"  ANSM:    {len(drug_chunks):>6} chunks")
    print(f"  HAS:     {len(has_chunks):>6} chunks")
    print(f"  TOTAL:   {len(all_chunks):>6} chunks")

    # Compute embeddings
    print(f"\n[3/5] Computing embeddings (multilingual-e5-base, {len(all_chunks)} texts)...")
    texts = [c["text"] for c in all_chunks]
    vectors = embed_passages_batch(texts, batch_size=64)
    print(f"  Embedding dimension: {len(vectors[0])}")

    # Prepare points for Qdrant
    print("\n[4/5] Preparing Qdrant points...")
    points = []
    for chunk, vector in zip(all_chunks, vectors):
        sparse_indices, sparse_values = _compute_bm25_sparse(chunk["text"])
        points.append({
            "id": _deterministic_uuid(chunk["text"]),
            "dense_vector": vector,
            "sparse_indices": sparse_indices,
            "sparse_values": sparse_values,
            "payload": chunk,
        })

    # Upsert to Qdrant
    print(f"[5/5] Upserting {len(points)} points to Qdrant...")
    total = upsert_points(points, batch_size=100)
    print(f"  Upserted: {total} points")

    # Verify
    info = get_collection_info()
    print(f"\nCollection '{info['name']}': {info['points_count']} points, status={info['status']}")
    print("\nDone.")


if __name__ == "__main__":
    main()
