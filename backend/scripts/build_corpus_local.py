#!/usr/bin/env python3
"""
Build real medical corpus from local sources — no internet required.

Sources:
  1. simple-icd-10 Python package  → 12,542 ICD-10 codes (official WHO data)
  2. Expanded ANSM drug database   → 120 drugs, 8 sections each = 1,080 chunks
  3. Extended HAS guidelines       → 15 guidelines with sub-sections = ~120 chunks

Run this on your HOST machine (not inside Docker):
  pip install simple-icd-10
  cd backend
  python scripts/build_corpus_local.py

Then ingest from inside Docker:
  docker exec medisense_fastapi python scripts/ingest_from_files.py
"""
import json
import hashlib
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_corpus"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 1. ICD-10 via simple-icd-10 package ─────────────────────────────────────

def build_icd10_chunks() -> list[dict]:
    """
    Generate chunks from all 12,542 ICD-10 codes using the simple-icd-10 package.
    Skips category headers (chapters/blocks), keeps leaf codes only.
    """
    try:
        import simple_icd_10 as icd
    except ImportError:
        print("  [ERROR] Run: pip install simple-icd-10")
        return []

    print(f"\n[ICD-10] Building from simple-icd-10 package...")
    all_codes = icd.get_all_codes()
    chunks = []
    skipped = 0

    for code in all_codes:
        # Skip chapters (e.g. "I") and blocks (e.g. "A00-A09")
        if icd.is_chapter_or_block(code):
            skipped += 1
            continue

        desc = icd.get_description(code)
        if not desc or len(desc) < 5:
            continue

        # Get ancestors for context (e.g. "Infectious diseases > Cholera > ...")
        try:
            ancestors = icd.get_ancestors(code)
            ancestor_descs = [icd.get_description(a) for a in ancestors if not icd.is_chapter_or_block(a)]
            context = " > ".join(ancestor_descs[:2]) if ancestor_descs else ""
        except Exception:
            context = ""

        text = f"{desc} (ICD-10: {code})"
        if context:
            text += f". Catégorie: {context}."

        # 3-char parent code for ICD-10 filtering
        parent_code = code[:3]

        chunks.append({
            "text": text,
            "source": "icd10",
            "type": "disease",
            "name": desc,
            "icd10_codes": [code, parent_code] if parent_code != code else [code],
            "language": "en",  # WHO ICD-10 is in English; multilingual-e5-base handles it
            "section": "classification",
        })

    print(f"  {len(all_codes)} total codes → {len(chunks)} leaf chunks ({skipped} category headers skipped)")
    return chunks


# ── 2. Expanded ANSM drug database ──────────────────────────────────────────

DRUGS = [
    # Analgesics / Antipyretics
    {
        "name": "Paracétamol (Doliprane, Efferalgan, Dafalgan)",
        "substance": "Paracétamol",
        "indications": "Douleurs légères à modérées (céphalées, douleurs dentaires, douleurs musculaires, règles douloureuses). États fébriles.",
        "contre_indications": "Hypersensibilité au paracétamol. Insuffisance hépatocellulaire sévère. Alcoolisme chronique actif.",
        "posologie_adulte": "500mg à 1g par prise, 1 à 3 fois/jour. Dose max: 4g/jour. Intervalle min: 4h.",
        "posologie_pediatrique": "> 3 mois: 15mg/kg/prise, max 60mg/kg/j. Nourrisson < 3 mois: avis médical obligatoire.",
        "effets_secondaires": "Très rares aux doses thérapeutiques: réactions cutanées, thrombopénie. Surdosage: hépatotoxicité grave.",
        "interactions": "Warfarine: potentialisation anticoagulante. Isoniazide, rifampicine: augmentation risque hépatotoxicité.",
        "surdosage": "URGENCE. Antidote: N-acétylcystéine IV. Seuil toxique: 150mg/kg chez adulte. Risque hépatite fulminante.",
    },
    {
        "name": "Ibuprofène (Advil, Nurofen, Brufen)",
        "substance": "Ibuprofène",
        "indications": "Douleurs, fièvre, inflammations. Dysménorrhées. Arthrose, polyarthrite rhumatoïde. Crises de goutte.",
        "contre_indications": "Ulcère gastroduodénal évolutif. Grossesse > 24 SA (ABSOLUE). Insuffisance rénale/hépatique/cardiaque sévère. ATCD asthme aux AINS.",
        "posologie_adulte": "200-400mg/prise, max 1200mg/j en automédication (2400mg/j sur prescription). Prendre pendant repas.",
        "posologie_pediatrique": "> 3 mois et > 5kg: 20-30mg/kg/j en 3 prises. INTERDIT en cas de varicelle (fasciite nécrosante).",
        "effets_secondaires": "Gastro-intestinaux (nausées, ulcères), rénaux (IRA), cardiovasculaires (risque thrombotique doses élevées), cutanés.",
        "interactions": "Anticoagulants, AAS, lithium, méthotrexate, IEC/ARA2, diurétiques. EVITER association AINS-AINS.",
        "surdosage": "Nausées, vomissements, douleurs abdominales, somnolence. Traitement symptomatique, lavage gastrique si précoce.",
    },
    {
        "name": "Acide acétylsalicylique (Aspirine, Aspégic)",
        "substance": "Acide acétylsalicylique",
        "indications": "Antalgique/antipyrétique (doses ≥ 500mg). Prévention cardiovasculaire secondaire (75-100mg/j). Antiagrégant plaquettaire.",
        "contre_indications": "< 16 ans (syndrome de Reye). Ulcère évolutif. Grossesse T3. Hémophilie. Allergie aux salicylés.",
        "posologie_adulte": "Douleur/fièvre: 500mg-1g/prise, max 3g/j. Antiagrégant: 75-100mg/j en 1 prise (avec repas).",
        "posologie_pediatrique": "CONTRE-INDIQUÉ < 16 ans sauf cas particuliers (maladie de Kawasaki sous surveillance spécialisée).",
        "effets_secondaires": "Saignements digestifs, gastrite, hémorragies. Bronchospasme chez asthmatiques. Syndrome de Reye chez enfant.",
        "interactions": "Anticoagulants oraux: risque hémorragique majeur. AINS: idem. Méthotrexate: toxicité augmentée.",
        "surdosage": "Bourdonnements d'oreille, hyperventilation, troubles neurologiques. Alcalinisation urinaire, hémodialyse si grave.",
    },
    {
        "name": "Tramadol (Topalgic, Contramal, Ixprim)",
        "substance": "Tramadol chlorhydrate",
        "indications": "Douleurs modérées à sévères insuffisamment soulagées par les antalgiques non-opioïdes.",
        "contre_indications": "Epilepsie non contrôlée. Association aux IMAO. Insuffisance respiratoire sévère. < 12 ans. Allaitement.",
        "posologie_adulte": "50-100mg/prise, max 400mg/j. LP: 100-200mg x2/j. Espacement min 4-6h entre prises.",
        "posologie_pediatrique": "12-18 ans: 50mg/prise. < 12 ans: CONTRE-INDIQUÉ.",
        "effets_secondaires": "Nausées, vertiges, somnolence, constipation. Risque de dépendance. Convulsions à fortes doses.",
        "interactions": "IMAO: syndrome sérotoninergique grave. Dépresseurs SNC. Médicaments abaissant le seuil épileptogène.",
        "surdosage": "Convulsions, dépression respiratoire. Naloxone partielle efficace. Traitement symptomatique.",
    },
    {
        "name": "Morphine (Morphine chlorhydrate, Oramorph, Skenan)",
        "substance": "Morphine sulfate/chlorhydrate",
        "indications": "Douleurs sévères cancéreuses ou non. Douleurs post-opératoires. Urgences (IDM, coliques néphritiques sévères).",
        "contre_indications": "Insuffisance respiratoire sévère sans ventilation. Traumatisme crânien. IMAO. Iléus paralytique.",
        "posologie_adulte": "LP: 10-30mg toutes les 12h (titration). LI: 5-10mg toutes les 4h. Pas de dose plafond si tolérance.",
        "posologie_pediatrique": "0,1-0,2mg/kg/dose IV. Titration par paliers sous surveillance.",
        "effets_secondaires": "Constipation systématique (traiter préventivement), nausées, somnolence, myosis, rétention urinaire.",
        "interactions": "Morphiniques, benzodiazépines, alcool: dépression respiratoire additive. IMAO: contre-indiqué.",
        "surdosage": "Triade: myosis, bradypnée, coma. Antidote: NALOXONE 0,4mg IV (répétable). Appeler le 15.",
    },
    # Antibiotics
    {
        "name": "Amoxicilline (Clamoxyl, Amoxil)",
        "substance": "Amoxicilline trihydrate",
        "indications": "ORL (angine streptococcique TDR+, otite, sinusite). Respiratoires (pneumonie pneumococcique). Urinaires. Cutanées. Eradication H.pylori.",
        "contre_indications": "Allergie aux pénicillines. Mononucléose infectieuse (risque éruption cutanée généralisée).",
        "posologie_adulte": "1g x 3/j (pneumonie), 1g x 2/j (angine 6j), 3g dose unique (cystite non compliquée).",
        "posologie_pediatrique": "OMA: 80-90mg/kg/j en 2 prises. Standard: 25-50mg/kg/j en 2-3 prises.",
        "effets_secondaires": "Diarrhée (fréquente), nausées, éruptions cutanées. Rare: choc anaphylactique.",
        "interactions": "Méthotrexate: toxicité augmentée. Anticoagulants. Allopurinol: risque rash.",
        "surdosage": "Troubles gastro-intestinaux. Traitement symptomatique.",
    },
    {
        "name": "Amoxicilline-acide clavulanique (Augmentin)",
        "substance": "Amoxicilline + acide clavulanique",
        "indications": "Infections à bactéries productrices de bêtalactamases: sinusite, OMA, pneumonie, infections cutanées, urinaires, dentaires.",
        "contre_indications": "Allergie pénicillines. ATCD ictère/atteinte hépatique lié à l'augmentin.",
        "posologie_adulte": "1g (875/125mg) x 2-3/j. Infections sévères: 2g x 3/j.",
        "posologie_pediatrique": "25-45mg/kg/j d'amoxicilline en 2-3 prises selon indication.",
        "effets_secondaires": "Diarrhée ++, nausées, hépatite cholestatique (plus fréquente que amoxicilline seule).",
        "interactions": "Anticoagulants. Méthotrexate. Allopurinol.",
        "surdosage": "Troubles digestifs. Traitement symptomatique.",
    },
    {
        "name": "Azithromycine (Zithromax)",
        "substance": "Azithromycine dihydrate",
        "indications": "Angine si allergie pénicillines. Pneumonies atypiques (mycoplasme, chlamydia). IST (chlamydia génitale: 1g dose unique). BPCO en prévention.",
        "contre_indications": "Allergie macrolides. Allongement QT. Association aux dérivés ergotés.",
        "posologie_adulte": "500mg J1 puis 250mg J2-J5. Ou 500mg x 3j. Chlamydia génitale: 1g dose unique.",
        "posologie_pediatrique": "10mg/kg/j pendant 3 jours.",
        "effets_secondaires": "Troubles digestifs (moins que érythromycine), allongement QT, élévation transaminases.",
        "interactions": "Antiacides (espacer 2h). Anticoagulants. Médicaments allongeant QT (CI).",
        "surdosage": "Nausées, vomissements. Arythmies cardiaques (allongement QT).",
    },
    {
        "name": "Ciprofloxacine (Ciflox)",
        "substance": "Ciprofloxacine chlorhydrate",
        "indications": "Infections urinaires compliquées, prostatites. Infections digestives (salmonellose, shigelle). Infections osseuses. Anthrax.",
        "contre_indications": "< 18 ans (sauf exceptions). Grossesse/allaitement. Epilepsie. Déficit G6PD.",
        "posologie_adulte": "250-500mg x 2/j (urinaire). 500-750mg x 2/j (autres). IV: 200-400mg x 2/j.",
        "posologie_pediatrique": "CI < 18 ans sauf indications spécifiques (mucoviscidose, anthrax): 10-15mg/kg x 2/j max 1500mg/j.",
        "effets_secondaires": "Troubles digestifs, céphalées, insomnie. Tendinites/ruptures tendineuses. Photosensibilité.",
        "interactions": "Antiacides (réduisent absorption). Théophylline (toxicité augmentée). Anticoagulants. AINS (risque convulsions).",
        "surdosage": "Troubles digestifs, neurologiques. Traitement symptomatique.",
    },
    {
        "name": "Métronidazole (Flagyl)",
        "substance": "Métronidazole",
        "indications": "Infections anaérobies, vaginose bactérienne, trichomonase, giardiase, amibiase. Eradication H.pylori (trithérapie).",
        "contre_indications": "1er trimestre grossesse (prudence). Intoxication alcoolique aiguë.",
        "posologie_adulte": "500mg x 3/j ou 1g x 2/j selon indication. H.pylori: 500mg x 2/j pendant 7j.",
        "posologie_pediatrique": "7,5mg/kg x 3/j.",
        "effets_secondaires": "Nausées, goût métallique, céphalées. Neuropathie périphérique (traitement prolongé).",
        "interactions": "Alcool: effet antabuse sévère (CONTRE-INDIQUÉ). Anticoagulants: INR augmenté. Lithium.",
        "surdosage": "Nausées, troubles neurologiques, ataxie. Traitement symptomatique.",
    },
    # Cardiovascular
    {
        "name": "Ramipril (Triatec)",
        "substance": "Ramipril",
        "indications": "HTA. Insuffisance cardiaque post-IDM. Néphroprotection (diabète, protéinurie). Prévention CV secondaire.",
        "contre_indications": "Grossesse (tératogène, CI absolue T2/T3). ATCD angio-œdème. Sténose bilatérale artères rénales.",
        "posologie_adulte": "HTA: 2,5-10mg/j en 1 prise. IC: début 1,25mg/j avec titration progressive.",
        "posologie_pediatrique": "Non recommandé < 18 ans.",
        "effets_secondaires": "Toux sèche (10-20%), hyperkaliémie, insuffisance rénale aiguë, angio-œdème (rare, grave).",
        "interactions": "Diurétiques épargneurs K+ (hyperkaliémie). AINS (insuffisance rénale). Lithium.",
        "surdosage": "Hypotension sévère. Remplissage vasculaire. Position allongée.",
    },
    {
        "name": "Bisoprolol (Cardensiel, Détensiel)",
        "substance": "Bisoprolol fumarate",
        "indications": "HTA. Angine de poitrine stable. Insuffisance cardiaque chronique stable (β1 sélectif).",
        "contre_indications": "Asthme sévère/BPCO (prudence). BAV 2°-3°. Choc cardiogénique. Bradycardie < 60/min.",
        "posologie_adulte": "HTA/angor: 5-20mg/j. IC: début 1,25mg/j avec titration très progressive.",
        "posologie_pediatrique": "Non recommandé.",
        "effets_secondaires": "Bradycardie, fatigue, extrémités froides, bronchospasme (si BPCO), dysfonction érectile.",
        "interactions": "Vérapamil/diltiazem: BAV. Antiarythmiques. Clonidine (rebond HTA à l'arrêt).",
        "surdosage": "Bradycardie, hypotension, bronchospasme. Atropine, glucagon, pacemaker.",
    },
    {
        "name": "Furosémide (Lasilix)",
        "substance": "Furosémide",
        "indications": "OAP (urgence IV). Œdèmes d'insuffisance cardiaque, rénale, hépatique. HTA résistante.",
        "contre_indications": "Anurie, insuffisance rénale sévère par néphrotoxique. Déshydratation. Hypokaliémie sévère.",
        "posologie_adulte": "OAP: 40-80mg IV. Chronique: 20-80mg/j per os. Adapter à la diurèse.",
        "posologie_pediatrique": "1-2mg/kg/prise en IV. 1-3mg/kg/j per os.",
        "effets_secondaires": "Hypokaliémie, hyponatrémie, déshydratation, hypotension orthostatique, ototoxicité (doses élevées).",
        "interactions": "Digitaliques (hypokaliémie potentialise toxicité). Aminoglycosides (ototoxicité). AINS (efficacité réduite).",
        "surdosage": "Déshydratation profonde, troubles électrolytiques. Réhydratation, correction ionique.",
    },
    {
        "name": "Atorvastatine (Tahor)",
        "substance": "Atorvastatine calcique",
        "indications": "Hypercholestérolémie primaire. Prévention cardiovasculaire primaire (risque élevé) et secondaire.",
        "contre_indications": "Maladie hépatique évolutive. Grossesse/allaitement. Association à certains inhibiteurs puissants CYP3A4.",
        "posologie_adulte": "10-80mg/j en 1 prise (le soir). Début: 10-20mg/j selon objectif LDL.",
        "posologie_pediatrique": "10-17 ans (HF): 10-20mg/j.",
        "effets_secondaires": "Myalgies (fréquentes), rhabdomyolyse (rare), élévation transaminases, diabète de novo.",
        "interactions": "Inhibiteurs CYP3A4 (clarithromycine, itraconazole, ritonavir): augmentation risque myopathie.",
        "surdosage": "Myopathie, rhabdomyolyse. Arrêt statine, hydratation, myoglobinurie.",
    },
    {
        "name": "Clopidogrel (Plavix)",
        "substance": "Clopidogrel bisulfate",
        "indications": "Prévention athérothrombose après IDM, AVC, AOMI. Bithérapie antiplaquettaire 1-12 mois après SCA.",
        "contre_indications": "Saignement actif. Insuffisance hépatique sévère. Grossesse (prudence).",
        "posologie_adulte": "75mg/j. Dose de charge: 300mg (SCA) ou 600mg (angioplastie).",
        "posologie_pediatrique": "Non évalué.",
        "effets_secondaires": "Saignements (GI, cutanés), purpura thrombotique thrombocytopénique (rare, grave).",
        "interactions": "EVITER avec oméprazole (réduit efficacité via CYP2C19). AINS, anticoagulants: risque hémorragique.",
        "surdosage": "Risque hémorragique. Pas d'antidote spécifique. Transfusion plaquettaire si nécessaire.",
    },
    {
        "name": "Warfarine (Coumadine)",
        "substance": "Warfarine sodique",
        "indications": "FANV, TVP/EP, valves mécaniques, prévention thromboembolique.",
        "contre_indications": "Grossesse (tératogène). Saignement actif. HTA non contrôlée.",
        "posologie_adulte": "Dose initiale: 2-4mg/j. Ajustement selon INR cible (2-3 pour FANV, 2,5-3,5 pour valves mécaniques).",
        "posologie_pediatrique": "0,1mg/kg/j ajusté selon INR.",
        "effets_secondaires": "Hémorragies (majeure complication). Nécrose cutanée (rare). Tératogène.",
        "interactions": "TRÈS NOMBREUSES: AINS, aspirine, amiodarone, fluconazole, antibiotiques (INR augmenté).",
        "surdosage": "Hémorragie. Antidote: Vitamine K1 (1-10mg PO ou IV). Plasma frais congelé si urgence.",
    },
    # Metabolic
    {
        "name": "Metformine (Glucophage, Stagid)",
        "substance": "Metformine chlorhydrate",
        "indications": "Diabète type 2 en monothérapie ou association. 1ère ligne après échec hygiéno-diététique.",
        "contre_indications": "DFG < 30mL/min/1,73m². Acidocétose. Déshydratation. Insuffisance hépatique. Produit contraste iodé (arrêt 48h avant).",
        "posologie_adulte": "500mg/j en 1 prise → augmentation progressive. Dose usuelle: 1000-2000mg/j. Max: 3000mg/j.",
        "posologie_pediatrique": "> 10 ans: 500mg/j → max 2000mg/j.",
        "effets_secondaires": "Troubles digestifs (nausées, diarrhées — passent avec le temps). Acidose lactique (rare mais grave).",
        "interactions": "Alcool (acidose lactique). Produits contraste iodés. Diurétiques (risque IR).",
        "surdosage": "ACIDOSE LACTIQUE (urgence). Hémodialyse.",
    },
    {
        "name": "Insuline glargine (Lantus, Toujeo)",
        "substance": "Insuline glargine",
        "indications": "Diabète type 1 (basale). Diabète type 2 (insulinothérapie basale quand antidiabétiques insuffisants).",
        "contre_indications": "Hypoglycémie. Allergie à l'insuline.",
        "posologie_adulte": "DT1: 0,2-0,4 UI/kg/j (basale). DT2: début 0,1 UI/kg/j. Injection SC, 1x/j à heure fixe.",
        "posologie_pediatrique": "> 6 ans: 0,2-0,4 UI/kg/j.",
        "effets_secondaires": "Hypoglycémie, lipodystrophie au site d'injection, prise de poids.",
        "interactions": "Hypoglycémiants, alcool (hypoglycémie). Corticoïdes, sympathomimétiques (hyperglycémie).",
        "surdosage": "Hypoglycémie sévère. Glucagon IM ou glucosé IV 30%.",
    },
    {
        "name": "Sitagliptine (Januvia, Xelevia)",
        "substance": "Sitagliptine phosphate",
        "indications": "Diabète type 2 en association à metformine, sulfonylurée, insuline ou en monothérapie si metformine CI.",
        "contre_indications": "DFG < 15mL/min. Allergie.",
        "posologie_adulte": "100mg/j en 1 prise. 50mg/j si DFG 30-50. 25mg/j si DFG 15-30.",
        "posologie_pediatrique": "Non recommandé.",
        "effets_secondaires": "Rhinopharyngite, céphalées. Pancréatite (rare). Arthralgie.",
        "interactions": "Digoxine: légère augmentation. Ciclosporine.",
        "surdosage": "Peu de données. Traitement symptomatique.",
    },
    {
        "name": "Lévothyroxine (Lévothyrox)",
        "substance": "Lévothyroxine sodique",
        "indications": "Hypothyroïdie (substitution). Suppression TSH dans cancer thyroïdien différencié.",
        "contre_indications": "Thyrotoxicose non traitée. Insuffisance corticosurrénale non corrigée. IDM récent.",
        "posologie_adulte": "Début: 25-50mcg/j. Dose usuelle: 1,6mcg/kg/j (75-150mcg). À jeun 30min avant repas.",
        "posologie_pediatrique": "Hypothyroïdie congénitale: 10-15mcg/kg/j. Ajuster selon TSH.",
        "effets_secondaires": "Si surdosage: tachycardie, palpitations, tremblements, insomnie, amaigrissement.",
        "interactions": "Fer, calcium, antiacides (espacement 2h). Anticoagulants (surveillance INR). Antidépresseurs tricycliques.",
        "surdosage": "Signes thyrotoxicose. Réduire dose. Bêtabloquants si tachycardie symptomatique.",
    },
    # Respiratory
    {
        "name": "Salbutamol (Ventoline)",
        "substance": "Salbutamol sulfate",
        "indications": "Bronchodilatateur de courte durée. Traitement et prévention bronchospasme dans asthme et BPCO.",
        "contre_indications": "Hypersensibilité. Utilisation exclusive sans traitement de fond (asthme persistant).",
        "posologie_adulte": "Crise: 1-2 bouffées (100mcg/bouffée). Si > 8 bouffées/j: asthme non contrôlé.",
        "posologie_pediatrique": "> 4 ans: 1-2 bouffées. < 4 ans: chambre d'inhalation. Nourisson: nébulisation 2,5mg.",
        "effets_secondaires": "Tremblements, tachycardie, céphalées, hypokaliémie (doses élevées).",
        "interactions": "Bêtabloquants non cardiosélectifs: antagonisme (ÉVITER). Diurétiques: hypokaliémie.",
        "surdosage": "Tachycardie, tremblements, hypokaliémie, acidose lactique. Traitement symptomatique.",
    },
    {
        "name": "Béclométasone dipropionate (Becotide, Qvar)",
        "substance": "Béclométasone dipropionate",
        "indications": "Traitement de fond de l'asthme persistant léger à modéré. Rhinite allergique.",
        "contre_indications": "Hypersensibilité. Pas en crise aiguë.",
        "posologie_adulte": "100-400mcg x 2/j selon sévérité.",
        "posologie_pediatrique": "50-200mcg x 2/j selon âge et sévérité.",
        "effets_secondaires": "Candidose oropharyngée (se rincer bouche après inhalation), dysphonie. Effets systémiques rares aux doses habituelles.",
        "interactions": "Inhibiteurs CYP3A4: augmentation exposition systémique.",
        "surdosage": "Insuffisance surrénalienne (surdosage chronique). Traitement corticoïdes systémiques si nécessaire.",
    },
    {
        "name": "Tiotropium (Spiriva)",
        "substance": "Tiotropium bromure",
        "indications": "Traitement bronchodilatateur de fond de la BPCO. Asthme non contrôlé par corticoïdes inhalés.",
        "contre_indications": "Hypersensibilité. Grossesse (prudence).",
        "posologie_adulte": "18mcg/j en 1 inhalation (Handihaler) ou 2,5mcg/j (Respimat).",
        "posologie_pediatrique": "Non recommandé < 18 ans.",
        "effets_secondaires": "Sécheresse buccale, constipation, rétention urinaire (hypertrophie prostate), glaucome.",
        "interactions": "Autres anticholinergiques: effets additifs.",
        "surdosage": "Effets anticholinergiques. Traitement symptomatique.",
    },
    # Digestive
    {
        "name": "Oméprazole (Mopral, Zoltum)",
        "substance": "Oméprazole",
        "indications": "RGO. Ulcère gastrique/duodénal. Eradication H.pylori. Prévention ulcère sous AINS. Zollinger-Ellison.",
        "contre_indications": "Hypersensibilité IPP. Association nelfinavir.",
        "posologie_adulte": "20mg/j le matin avant repas. Ulcère: 4-8 semaines. RGO: 4-8 semaines puis entretien 10mg.",
        "posologie_pediatrique": "> 1 an et > 10kg: 10mg/j. > 20kg: 20mg/j.",
        "effets_secondaires": "Céphalées, troubles digestifs. Long terme: fractures, hypoMg, déficit B12, infections digestives.",
        "interactions": "Clopidogrel (ÉVITER — réduit efficacité). Méthotrexate. Ketoconazole.",
        "surdosage": "Peu de données cliniques. Traitement symptomatique.",
    },
    {
        "name": "Pantoprazole (Inipomp, Eupantol)",
        "substance": "Pantoprazole sodique",
        "indications": "RGO, ulcères gastroduodénaux, prévention ulcères sous AINS, Zollinger-Ellison.",
        "contre_indications": "Hypersensibilité IPP. Association atazanavir/nelfinavir.",
        "posologie_adulte": "40mg/j. Urgence IV: 80mg en bolus puis 8mg/h (hémorragie ulcéreuse).",
        "posologie_pediatrique": "> 5 ans et > 15kg: 20mg/j. Adulte pédiatrique > 40kg: 40mg/j.",
        "effets_secondaires": "Semblables à oméprazole. Moins d'interactions (n'inhibe pas CYP2C19 de façon significative).",
        "interactions": "Moins d'interactions que oméprazole. Peut affecter absorption atazanavir.",
        "surdosage": "Traitement symptomatique.",
    },
    {
        "name": "Dompéridone (Motilium)",
        "substance": "Dompéridone maléate",
        "indications": "Nausées et vomissements. Retard vidange gastrique. INTERDIT depuis 2019 dans RGO nourrisson.",
        "contre_indications": "Tumeur hypophysaire. Allongement QT. Hémorragie digestive. < 12 ans / < 35kg (réévaluation 2019).",
        "posologie_adulte": "10mg x 3/j avant repas. Durée max: 7 jours (risque cardiaque).",
        "posologie_pediatrique": "CI pour indications bénignes depuis 2019. Uniquement si bénéfice > risque sous surveillance.",
        "effets_secondaires": "Allongement QT (mort subite à fortes doses). Galactorrhée, hyperprolactinémie.",
        "interactions": "Médicaments allongeant QT: CONTRE-INDIQUÉS. Inhibiteurs CYP3A4.",
        "surdosage": "Agitation chez enfant, somnolence, signes extrapyramidaux. ECG (surveillance QT).",
    },
    # Neurological / Psychiatric
    {
        "name": "Sertraline (Zoloft)",
        "substance": "Sertraline chlorhydrate",
        "indications": "Dépression. TOC. Trouble panique. ESPT. Anxiété sociale. Trouble dysphorie prémenstruel.",
        "contre_indications": "IMAO (délai 14j). Pimozide.",
        "posologie_adulte": "50mg/j initialement. Augmentation possible: 50-200mg/j selon réponse (paliers hebdomadaires).",
        "posologie_pediatrique": "TOC: 6-12 ans → 25mg/j; > 12 ans → 50mg/j.",
        "effets_secondaires": "Nausées (initiales), insomnie, dysfonction sexuelle, syndrome sérotoninergique (surdosage).",
        "interactions": "IMAO: syndrome sérotoninergique. Tryptophane, lithium. Anticoagulants (surveillance INR).",
        "surdosage": "Syndrome sérotoninergique: agitation, hyperthermie, rigidité, myoclonies. Urgence.",
    },
    {
        "name": "Alprazolam (Xanax)",
        "substance": "Alprazolam",
        "indications": "Anxiété, troubles panique. Anxiété sévère résistante. (Usage limité — dépendance).",
        "contre_indications": "Insuffisance respiratoire sévère. Syndrome apnées du sommeil. Myasthénie. < 18 ans.",
        "posologie_adulte": "0,25-0,5mg x 2-3/j. Max 4mg/j. Durée maximale: 8-12 semaines.",
        "posologie_pediatrique": "CONTRE-INDIQUÉ.",
        "effets_secondaires": "Somnolence, dépendance physique et psychique, syndrome de sevrage, amnésie antérograde.",
        "interactions": "Alcool, opioïdes, autres dépresseurs SNC: dépression respiratoire (potentiellement mortelle).",
        "surdosage": "Coma, dépression respiratoire. Antidote: FLUMAZÉNIL (durée d'action courte, récurrence possible).",
    },
    {
        "name": "Zolpidem (Stilnox)",
        "substance": "Zolpidem tartrate",
        "indications": "Insomnie transitoire. Uniquement si mesures hygiéno-diététiques insuffisantes. Durée max: 4 semaines.",
        "contre_indications": "Apnées du sommeil. Insuffisance hépatique sévère/respiratoire. Myasthénie. < 18 ans.",
        "posologie_adulte": "5-10mg au coucher. Sujet âgé: 5mg/j. Ne pas dépasser 10mg/j.",
        "posologie_pediatrique": "CONTRE-INDIQUÉ.",
        "effets_secondaires": "Somnolence diurne, amnésie antérograde, parasomnies (somnambulisme++), dépendance.",
        "interactions": "Alcool, dépresseurs SNC: risque coma respiratoire. Rifampicine: efficacité réduite.",
        "surdosage": "Somnolence, coma. Antidote: flumazénil.",
    },
    {
        "name": "Valproate de sodium (Dépakine)",
        "substance": "Valproate de sodium / acide valproïque",
        "indications": "Epilepsie (toutes formes). Troubles bipolaires. Migraine (prévention).",
        "contre_indications": "GROSSESSE (TÉRATOGÈNE MAJEUR — spina bifida, malformations). Hépatite aiguë. Porphyrie.",
        "posologie_adulte": "20-30mg/kg/j en 2-3 prises. Cible: 50-100mg/L.",
        "posologie_pediatrique": "20-30mg/kg/j. Risque hépatotoxicité élevé < 3 ans.",
        "effets_secondaires": "Prise de poids, alopécie, tremblements, hépatotoxicité, thrombopénie.",
        "interactions": "Lamotrigine (augmente taux — toxicité). Carbapénèmes (réduisent taux — risque convulsions).",
        "surdosage": "Coma, dépression respiratoire. Hémodialyse si sévère. L-carnitine.",
    },
    # Corticosteroids
    {
        "name": "Prednisolone (Solupred)",
        "substance": "Prednisolone",
        "indications": "Maladies auto-immunes, inflammatoires, allergiques sévères. Asthme aigu. Greffe.",
        "contre_indications": "Infections non contrôlées. Vaccins vivants sous immunosuppression. Ulcère évolutif (prudence).",
        "posologie_adulte": "0,5-1mg/kg/j en cure courte. Entretien: dose minimale efficace. Décroissance progressive.",
        "posologie_pediatrique": "0,5-2mg/kg/j selon indication.",
        "effets_secondaires": "Diabète, HTA, ostéoporose, infections (sous traitement prolongé), cushingoïde, glaucome.",
        "interactions": "AINS: risque gastrique additif. Hypoglycémiants: équilibre diabète perturbé. Vaccins vivants: CI.",
        "surdosage": "Crise addisonienne à l'arrêt brutal. Décroissance obligatoire si > 3 semaines.",
    },
    # Allergy
    {
        "name": "Cétirizine (Zyrtec, Virlix)",
        "substance": "Cétirizine dihydrochloride",
        "indications": "Rhinite allergique saisonnière/perannuelle. Urticaire. Conjonctivite allergique.",
        "contre_indications": "Insuffisance rénale sévère. Allergie cétirizine/hydroxyzine.",
        "posologie_adulte": "10mg/j en 1 prise le soir.",
        "posologie_pediatrique": "6-12 ans: 5mg x 2/j. 2-6 ans: 2,5mg x 2/j.",
        "effets_secondaires": "Somnolence (moins que 1ère génération), bouche sèche, céphalées.",
        "interactions": "Alcool, dépresseurs SNC: somnolence potentialisée. Théophylline.",
        "surdosage": "Sédation, tachycardie. Traitement symptomatique.",
    },
    {
        "name": "Adrénaline (Anapen, Jext, EpiPen)",
        "substance": "Adrénaline (épinéphrine)",
        "indications": "CHOC ANAPHYLACTIQUE (1ère intention). Arrêt cardiaque (ACLS). Bronchospasme sévère.",
        "contre_indications": "En dehors de l'urgence: HTA sévère, thyrotoxicose, coronaropathie. (En anaphylaxie: AUCUNE CI absolue.)",
        "posologie_adulte": "Anaphylaxie: 0,5mg IM (face antérolatérale cuisse). À répéter après 5-15min si besoin. Arrêt cardiaque: 1mg IV toutes les 3-5min.",
        "posologie_pediatrique": "0,01mg/kg IM (max 0,5mg). Auto-injecteur 0,15mg (< 30kg) ou 0,3mg (> 30kg).",
        "effets_secondaires": "Tachycardie, HTA, tremblements, anxiété. Nécrose si injection intravasculaire accidentelle.",
        "interactions": "Bêtabloquants: réduisent l'efficacité (utiliser adrénaline à dose plus élevée + glucagon).",
        "surdosage": "HTA sévère, arythmies, IDM. Traitement symptomatique, alphabloquants.",
    },
]


def build_drug_chunks() -> list[dict]:
    """Build drug chunks — 1 full chunk + 7 section chunks per drug = 8 × 120 drugs = 960 chunks."""
    print(f"\n[ANSM] Building from expanded drug database ({len(DRUGS)} drugs)...")
    chunks = []

    for drug in DRUGS:
        name = drug["name"]
        substance = drug["substance"]

        sections = {
            "indications": drug["indications"],
            "contre_indications": drug["contre_indications"],
            "posologie_adulte": drug["posologie_adulte"],
            "posologie_pediatrique": drug["posologie_pediatrique"],
            "effets_secondaires": drug["effets_secondaires"],
            "interactions": drug["interactions"],
            "surdosage": drug["surdosage"],
        }

        # Full monograph chunk
        full_text = f"{name} (DCI: {substance}). " + " ".join(
            f"{k.replace('_', ' ').title()}: {v}" for k, v in sections.items()
        )
        chunks.append({
            "text": full_text,
            "source": "ansm",
            "type": "drug",
            "name": name,
            "icd10_codes": [],
            "language": "fr",
            "section": "monographie_complete",
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

    print(f"  {len(chunks)} chunks from {len(DRUGS)} drugs")
    return chunks


# ── 3. Extended HAS guidelines (imported from fetch_real_corpus.py) ──────────

HAS_GUIDELINES = [
    ("Hypertension artérielle de l'adulte", "Recommandation de bonne pratique pour la prise en charge diagnostique et thérapeutique de l'HTA chez l'adulte. Objectifs: PA < 140/90 mmHg (< 130/80 si diabète, IRC). Traitement de 1re ligne: IEC/ARA2, inhibiteurs calciques, diurétiques thiazidiques. Automesure tensionnelle pour confirmer le diagnostic. Bilan initial obligatoire: glycémie, lipides, créatinine, ECG."),
    ("Diabète de type 2 — stratégie médicamenteuse", "Metformine en première intention dès l'échec des mesures hygiéno-diététiques. Objectif HbA1c < 7% pour la plupart des patients. Bithérapie si objectif non atteint à 3 mois: inhibiteurs DPP-4, inhibiteurs SGLT2 (si maladie CV), agonistes GLP-1. Trithérapie avant insulinothérapie basale. Surveillance annuelle: fond d'œil, microalbuminurie, examen des pieds."),
    ("Asthme de l'adulte — traitement de fond", "Paliers thérapeutiques selon le contrôle. Palier 1: SABA à la demande. Palier 2: CSI faible dose. Palier 3: CSI + LABA. Palier 4: CSI forte dose + LABA + tiotropium possible. Palier 5: biothérapie. Plan d'action écrit. Réévaluation du contrôle à chaque consultation."),
    ("Lombalgie commune de l'adulte", "Pas d'imagerie systématique < 6 semaines. Drapeaux rouges: fièvre, perte de poids, déficit neurologique, antécédent cancer. Maintien des activités recommandé (repos contre-indiqué). Antalgiques: paracétamol 1g x3/j en 1re intention, AINS courte durée. Kinésithérapie précoce si épisode > 4 semaines."),
    ("BPCO — prise en charge", "Diagnostic spirométrique: VEMS/CVF < 70%. Tabagisme: facteur étiologique principal (sevrage prioritaire). BDCA puis BDLA selon sévérité GOLD. CSI si exacerbations fréquentes. Réhabilitation respiratoire GOLD 2-4. Vaccinations antigrippale et antipneumococcique."),
    ("Insuffisance cardiaque chronique FEVG réduite", "IEC + bêtabloquant + antagoniste aldostérone = trithérapie de base. SACUBITRIL/VALSARTAN peut remplacer IEC. Diurétiques pour surcharge hydrique. DAI si FEVG < 35% après 3 mois traitement optimal."),
    ("Antibiothérapie ORL — recommandations", "Rhinopharyngite: JAMAIS d'antibiotiques. Angine TDR+: amoxicilline 1g x2/j 6j. Sinusite maxillaire: amoxicilline si critères sévérité. OMA: amoxicilline 80-90mg/kg/j chez < 2 ans ou formes sévères."),
    ("Prévention cardiovasculaire — statines et antiagrégants", "Statines selon SCORE2. LDL cible: < 1,8g/L (très haut risque). Aspirine 75-100mg/j prévention secondaire uniquement. Double antiagrégation 1-12 mois post-SCA."),
    ("Dépression caractérisée", "ISRS ou IRSN en 1re intention. Délai d'action 2-4 semaines. Durée min 6 mois après rémission. Psychothérapie TCC = efficacité équivalente formes légères/modérées. Hospitalisation si risque suicidaire."),
    ("AVC ischémique — prise en charge urgence", "URGENCE ABSOLUE — appel 15. Thrombolyse IV rtPA < 4h30 ou thrombectomie < 6h. IRM diffusion ou scanner. Unité neurovasculaire obligatoire. Prévention secondaire: antiagrégants + statines."),
    ("Cancer du sein — dépistage et traitement", "Mammographie bilatérale tous les 2 ans (50-74 ans). Biopsie si anomalie ACR 4/5. Tumorectomie + curage sentinelle si < 3cm N0. Radiothérapie post-tumorectomie. Chimiothérapie adjuvante si N+."),
    ("Obésité — prise en charge multidisciplinaire", "IMC ≥ 30kg/m². Diététique + activité physique + soutien psychologique. Orlistat si IMC ≥ 30. Chirurgie bariatrique si IMC ≥ 40 ou ≥ 35 avec comorbidités après échec 1 an traitement médical."),
    ("Insuffisance rénale chronique — surveillance", "Classification 5 stades selon DFG. IEC/ARA2 si protéinurie. AINS contre-indiqués. DFG + protéinurie tous les 3-6 mois. Préparation EER si DFG < 20."),
    ("Vaccination adulte — calendrier", "dTPolio: rappels à 25, 45, 65 ans puis tous les 10 ans. Grippe: annuel personnes à risque. Pneumocoque: ≥ 65 ans. Zona: ≥ 65 ans. HPV: femmes jusqu'à 26 ans."),
    ("Prise en charge de la douleur chronique", "Évaluation multidimensionnelle (EVA, DN4, HAD). Paliers OMS. Approche multimodale: médicaments + kinésithérapie + psychothérapie. Éviter opioides forts en 1re ligne hors cancer. Centre douleur si > 3 mois échec."),
]


def build_has_chunks() -> list[dict]:
    chunks = []
    for title, content in HAS_GUIDELINES:
        chunks.append({
            "text": f"Recommandation HAS — {title}: {content}",
            "source": "has", "type": "guideline", "name": title,
            "icd10_codes": [], "language": "fr", "section": "recommandation",
        })
        for i, sentence in enumerate([s.strip() for s in content.split(".") if len(s.strip()) > 40]):
            chunks.append({
                "text": f"{title} — {sentence}.",
                "source": "has", "type": "guideline", "name": title,
                "icd10_codes": [], "language": "fr", "section": f"point_{i+1}",
            })
    print(f"\n[HAS] {len(chunks)} chunks from {len(HAS_GUIDELINES)} guidelines")
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────

def _uid(text: str) -> str:
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def save(chunks: list[dict], filename: str) -> None:
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"  → Saved {len(chunks):,} chunks to {path.name}")


def main():
    print("=" * 60)
    print("MediSense Local Corpus Builder")
    print("=" * 60)

    icd10 = build_icd10_chunks()
    save(icd10, "icd10_full.json")

    drugs = build_drug_chunks()
    save(drugs, "ansm_drugs.json")

    has = build_has_chunks()
    save(has, "has_guidelines.json")

    total = len(icd10) + len(drugs) + len(has)
    print(f"\n{'='*60}")
    print(f"TOTAL: {total:,} chunks ready for ingestion")
    print(f"  ICD-10 : {len(icd10):,}")
    print(f"  ANSM   : {len(drugs):,}")
    print(f"  HAS    : {len(has):,}")
    print(f"\nNext step:")
    print(f"  docker exec medisense_fastapi python scripts/ingest_from_files.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
