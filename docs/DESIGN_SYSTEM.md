# MediSense AI — Design System & Full UI/UX Specification
**Version 1.0 | Sprint 9–10 | "Neural Dark" Design Language**

> Ce document couvre l'intégralité des flows, écrans, états et interactions
> pour les **4 rôles** (patient, médecin, secrétaire, admin) sur les **2 plateformes**
> (Flutter mobile + Next.js dashboard), dérivés directement de tous les endpoints API,
> modèles DB et cas d'utilisation du projet.

---

## Table des Matières

1. [Design Tokens — Le fondement](#1-design-tokens--le-fondement)
2. [Rôles & Périmètres d'accès](#2-rôles--périmètres-daccès)
3. [App Mobile Flutter — Patient](#3-app-mobile-flutter--patient)
4. [Dashboard Web Next.js — Médecin](#4-dashboard-web-nextjs--médecin)
5. [Dashboard Web Next.js — Secrétaire](#5-dashboard-web-nextjs--secrétaire)
6. [Dashboard Web Next.js — Admin](#6-dashboard-web-nextjs--admin)
7. [Composants partagés](#7-composants-partagés)
8. [États universels](#8-états-universels)
9. [Motion & Animation](#9-motion--animation)
10. [Accessibilité & RGPD by Design](#10-accessibilité--rgpd-by-design)

---

## 1. Design Tokens — Le fondement

### Couleurs

```
── Surfaces (dark-first) ──────────────────────────────────
surface-0   : #070B14   ← fond le plus profond (body, backgrounds)
surface-1   : #0F1623   ← cartes primaires, panels
surface-2   : #161E2E   ← cartes élevées, dropdowns
surface-3   : #1D2640   ← hover states, sélections

── Brand AI ────────────────────────────────────────────────
ai-from     : #6366F1   ← indigo (début gradient)
ai-to       : #8B5CF6   ← violet (fin gradient)
ai-glow     : #6366F1 @ 30% opacity → box-shadow

── Médicaux (convention internationale) ────────────────────
pulse-red   : #F43F5E   ← FC / fréquence cardiaque / urgence
oxygen-blue : #38BDF8   ← SpO2 / saturation
hrv-violet  : #A78BFA   ← HRV / variabilité cardiaque
temp-amber  : #FBBF24   ← température

── Risque no-show (identique backend) ──────────────────────
risk-safe   : #22C55E   ← < 20% probabilité
risk-warn   : #F97316   ← 20–40%
risk-danger : #EF4444   ← > 40%

── Statuts DPA ─────────────────────────────────────────────
status-pending  : #F59E0B
status-approved : #22C55E
status-modified : #38BDF8
status-rejected : #EF4444

── Texte ───────────────────────────────────────────────────
text-primary   : #F1F5F9   ← titres, contenu principal
text-secondary : #94A3B8   ← sous-titres, metadata
text-muted     : #475569   ← labels, disabled
text-inverse   : #0F1623   ← sur fond clair

── CRM Sync statuts ────────────────────────────────────────
crm-pending  : #F59E0B
crm-sent     : #22C55E
crm-failed   : #EF4444
crm-skipped  : #475569
crm-cb-open  : #F43F5E   ← circuit breaker ouvert
```

### Typographie

```
── Polices ─────────────────────────────────────────────────
display  : "Clash Display"    → titres, chiffres clés, splash
body     : "Inter"            → contenu, labels, descriptions
mono     : "JetBrains Mono"   → UUID, timestamps, scores, code

── Échelle de taille ───────────────────────────────────────
h1  : Clash Display  40px  weight 700  tracking -1px
h2  : Clash Display  28px  weight 600  tracking -0.5px
h3  : Inter          20px  weight 600
h4  : Inter          16px  weight 600
body-lg : Inter      16px  weight 400
body    : Inter      14px  weight 400
small   : Inter      12px  weight 400
micro   : Inter      11px  weight 400
mono-sm : JetBrains  12px  weight 400
```

### Espacement & Rayons

```
── Spacing (multiples de 4px) ──────────────────────────────
xs  : 4px    sm  : 8px    md  : 16px
lg  : 24px   xl  : 32px   2xl : 48px   3xl : 64px

── Border radius ───────────────────────────────────────────
sm   : 8px    md  : 12px   lg  : 16px
xl   : 20px   2xl : 24px   full: 9999px

── Shadows / Glow ──────────────────────────────────────────
card-shadow   : 0 4px 24px rgba(0,0,0,0.4)
ai-glow       : 0 0 20px rgba(99,102,241,0.3)
risk-glow-red : 0 0 12px rgba(239,68,68,0.5)
risk-glow-ora : 0 0 12px rgba(249,115,22,0.5)
risk-glow-grn : 0 0 12px rgba(34,197,94,0.4)
```

---

## 2. Rôles & Périmètres d'accès

```
┌─────────────────────────────────────────────────────────────┐
│  RÔLE      │  APP         │  ACCÈS COMPLET                  │
├────────────┼──────────────┼─────────────────────────────────┤
│  patient   │  Flutter     │  Chat, Appointments (lecture),  │
│            │              │  IoT Dashboard, Profil, RGPD    │
├────────────┼──────────────┼─────────────────────────────────┤
│  doctor    │  Next.js     │  Agenda, DPA (read+approve),    │
│            │              │  Patients (consent), Predict    │
├────────────┼──────────────┼─────────────────────────────────┤
│  secretary │  Next.js     │  Agenda, CRM Tasks,             │
│            │              │  SMS Dispatch, Feedback ML      │
├────────────┼──────────────┼─────────────────────────────────┤
│  admin     │  Next.js     │  TOUT : audit, users, export,   │
│            │              │  erasure, rerank eval, DPA      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. App Mobile Flutter — Patient

### 3.0 Navigation globale

```
FLUX COMPLET :

[Splash] ──→ has token? ──→ [Main Shell]
              ↓ non
           onboarded? ──→ [Onboarding] ──→ [Login] ──→ [Consent] ──→ [Main Shell]
              ↓ non
           [Login] ──────────────────────────────────────────────→ [Main Shell]


[Main Shell] contient 4 onglets :
  Tab 0 : [Chat]         → /home
  Tab 1 : [Rendez-vous]  → /appointments
  Tab 2 : [Biométrie]    → /iot
  Tab 3 : [Profil]       → /profile
```

---

### 3.1 Splash Screen

**Endpoints utilisés :** aucun (lecture secure storage seulement)

**Layout :**
```
┌────────────────────────────┐
│                            │
│                            │
│         ≋≋≋≋≋              │  ← waveform animée
│      5 barres verticales   │     (hauteur varie : 12/24/40/24/12px)
│      couleur : ai-from     │     animation : staggered, 400ms chacune
│                            │
│      MediSense AI          │  ← Clash Display h1, text-primary
│                            │
│  RAG · XGBoost · LSTM      │  ← Inter micro, text-muted, tracking 3px
│                            │
│                            │
└────────────────────────────┘
Background : surface-0 (#070B14)
Durée : 2.0s puis navigate
```

**Logique :**
```
1. read('access_token') + read('onboarded')
2. if token → /home
3. elif onboarded → /login
4. else → /onboarding
```

---

### 3.2 Onboarding (3 slides)

**Endpoints utilisés :** aucun

**Layout global :**
```
┌────────────────────────────┐
│                            │
│   [PageView horizontal]    │
│                            │
│   ┌──────────────────┐     │
│   │   ILLUSTRATION   │     │  ← Lottie animation ou SVG animé
│   │   (120x120px)    │     │
│   └──────────────────┘     │
│                            │
│   Titre (h2, Clash)        │
│   Description (body, muted)│
│                            │
│   ●  ○  ○                  │  ← dots indicator (gradient = active)
│                            │
│ [Passer]        [Suivant →]│  ← dernière slide: [Commencer]
└────────────────────────────┘
Background : surface-0
```

**Slide 1 — Biométrie IoT :**
- Animation : onde cardiaque qui se trace (dessin progressif)
- Titre : "Votre santé en temps réel"
- Desc : "Fréquence cardiaque, SpO2 et HRV suivis 24h/24 via vos capteurs connectés."

**Slide 2 — Chat IA :**
- Animation : bulle de chat avec curseur qui tape, puis réponse
- Titre : "Votre assistant médical IA"
- Desc : "Posez vos questions en français, arabe ou darija. L'IA analyse et répond avec sources médicales."

**Slide 3 — RGPD :**
- Animation : bouclier avec cadenas qui se ferme
- Titre : "Vos données, votre contrôle"
- Desc : "Chiffrement AES-256. Consentement granulaire. Droit à l'effacement. Conformité RGPD totale."

**CTA "Commencer" :**
- Bouton pleine largeur, gradient indigo→violet, rounded-full
- Action : write('onboarded', 'true') → navigate('/login')

---

### 3.3 Login Page

**Endpoints utilisés :** `POST /auth/login`

**Layout :**
```
┌────────────────────────────┐
│                            │
│         ≋≋≋               │  ← waveform mini (40px)
│   MediSense AI             │  ← h2, Clash Display
│   Connexion patient        │  ← body, text-secondary
│                            │
│   Email                    │  ← label Inter 12px text-muted
│   ┌─ email@exemple.ma ──┐  │  ← input: bg surface-2
│   └────────────────────┘  │     focus: bottom border gradient
│                            │
│   Mot de passe             │
│   ┌─ ••••••••••••••• 👁 ┐  │  ← password visibility toggle
│   └────────────────────┘  │
│                            │
│   [Erreur si existe]       │  ← bg rouge @ 10%, border rouge, texte F43F5E
│                            │
│ ┌──────────────────────┐   │
│ │   Se connecter   →   │   │  ← gradient button, rounded-full
│ └──────────────────────┘   │
│                            │
│  v1.0 · n.synergy · EMSI   │  ← micro, text-muted, center
└────────────────────────────┘
Background : surface-0
```

**États :**
- **idle** : formulaire normal
- **loading** : bouton affiche spinner + "Connexion…", inputs désactivés
- **error** : champ(s) bordure rouge, shake animation 200ms, message d'erreur
- **success** : navigate vers /consent (première fois) ou /home

**Erreurs possibles (from API) :**
- 401 `"Incorrect email or password"` → afficher en rouge
- 403 `"Account is deactivated"` → afficher en rouge + support link
- 422 validation → `"Email ou mot de passe incorrect"` (fallback)

---

### 3.4 Consent Page (RGPD)

**Endpoints utilisés :** `POST /patient/consent`

**Quand :** première connexion OU navigation depuis profil → "Gérer mes consentements"

**Layout :**
```
┌────────────────────────────┐
│  ← Retour         Ignorer  │  ← ignorer = consentements tous OFF
│                            │
│  🔒 Vos Consentements      │  ← h2 Clash Display
│  Contrôlez l'utilisation   │  ← body text-secondary
│  de vos données médicales. │
│                            │
│ ┌────────────────────────┐ │
│ │ 📡  Données biométriques│ │  ← card surface-1
│ │     IoT                 │ │     border left 3px ai-from si ON
│ │  FC, SpO2, HRV depuis   │ │     toggle droit
│ │  vos capteurs connectés │ │
│ │                [  ON  ] │ │
│ └────────────────────────┘ │
│                            │
│ ┌────────────────────────┐ │
│ │ 🤖  Assistant IA (NLP) │ │
│ │  Chat avec Mistral 7B  │ │
│ │  Analyse de symptômes  │ │
│ │                [ OFF ] │ │
│ └────────────────────────┘ │
│                            │
│ ┌────────────────────────┐ │
│ │ 🔗  Partage médecin    │ │
│ │  Partager avec votre   │ │
│ │  équipe soignante      │ │
│ │                [ OFF ] │ │
│ └────────────────────────┘ │
│                            │
│  Art. 7 RGPD · Modifiable  │  ← micro, text-muted
│  à tout moment             │
│                            │
│ ┌──────────────────────┐   │
│ │   Confirmer          │   │  ← gradient button
│ └──────────────────────┘   │
└────────────────────────────┘
```

**États toggle :**
- ON : border-left 3px gradient AI, fond surface-2, icône colorée
- OFF : border-left 3px surface-3, fond surface-1, icône muted

**Après confirmation :**
- Si consent_nlp = false → navigue vers /home avec banner "Chat IA désactivé"
- Si consent_nlp = true → navigue vers /home

---

### 3.5 Chat Page (US-48) — ÉCRAN PRINCIPAL

**Endpoints :**
- `POST /chat/stream` → streaming SSE token par token
- `GET /chat` → liste des conversations
- `GET /chat/{conversation_id}` → historique messages
- `DELETE /chat/{conversation_id}` → supprimer conversation

**Layout complet :**
```
┌────────────────────────────┐
│ ←   Assistant IA     ⋮    │  ← AppBar dark
│      ● En ligne           │  ← dot vert + "En ligne" text-muted
│                            │
├────────────────────────────┤
│ [URGENCY BANNER — si urgence]│  ← visible seulement si is_urgent
│  ⚠  Situation d'urgence   │
│     Appelez le 141 SAMU    │  ← pulsing icon, gradient rouge
├────────────────────────────┤
│                            │
│   [ÉTAT VIDE — pas de msg] │
│                            │
│     ≋  Bonjour Ahmed       │  ← nom from /auth/me
│   Posez votre question     │
│                            │
│  ┌────┐ ┌──────┐ ┌──────┐  │  ← suggestion chips
│  │ FR │ │  AR  │ │Darija│  │     surface-2, border gradient 1px
│  └────┘ └──────┘ └──────┘  │
│  "Mes symptômes"           │
│  "Mon traitement"          │  ← 3 chips de suggestion
│  "Urgence médicale"        │
│                            │
├────────────────────────────┤
│  [LISTE MESSAGES — scrollable]│
│                            │
│  ╔══════════════╗          │  ← Bulle assistant
│  ║ [▋ en cours] ║          │     surface-1, border-left 3px gradient
│  ╚══════════════╝          │     Curseur ▋ animé (blink 600ms)
│  [FR] ██░ 87%  3 sources   │  ← meta row : langue, confiance, sources
│                            │
│            ╔════════════╗  │  ← Bulle utilisateur
│            ║ Mon message║  │     gradient indigo→violet, white text
│            ╚════════════╝  │     radius asymétrique: 20,4,20,20
│                            │
├────────────────────────────┤
│  ┌──────────────────────┐  │
│  │  Décrivez vos        │  │  ← TextField surface-2, radius-full
│  │  symptômes…          │  │     maxLines: 6, expand on type
│  └──────────────────────┘  │
│  [🎤]              [  →  ] │  ← mic: gradient quand écoute
└────────────────────────────┘
```

**Bulle Assistant — détail :**
```
surface-1 (#0F1623)
Border-left : 3px gradient indigo→violet
               (animation: "voyageur lumineux" monte↕ en loop quand streaming)
Padding : 12px 16px
Radius : 4 20 20 20 (coin haut-gauche = 4px → pointe vers gauche)

[Texte en cours de stream] + curseur ▋ (clignote 600ms)
[Texte final] sans curseur

─── Meta row sous la bulle ─────────────────────────────────
[FR]         ← pill surface-3, Inter 10px
[████░] 87%  ← mini progress bar (ai-from color) + JetBrains Mono 10px
[3 sources]  ← tappable, ouvre SourcesBottomSheet
```

**Confiance → couleur :**
- ≥ 80% : risk-safe (vert)
- 60–79% : ai-from (indigo)
- 40–59% : risk-warn (orange)
- < 40% : risk-danger (rouge)

**Bulle Utilisateur — détail :**
```
LinearGradient(ai-from → ai-to)
Radius : 20 4 20 20 (coin haut-droit = 4px)
Padding : 12px 16px
Texte : text-inverse (dark on gradient)
```

**Urgency Banner :**
```
Position : sticky top (flottant sur les messages)
Background : gradient #F43F5E → #DC2626
Icon ⚠ : pulse animation 1.5s (scale 1.0→1.15→1.0)
"141 — SAMU Maroc" en Clash Display 18px white bold
Sous-texte : "Situation d'urgence détectée — appelez immédiatement"
```

**Voice Input (🎤) :**
```
État idle : icône mic, surface-2, radius-full 48px
État écoute :
  - Fond : gradient ai-from→ai-to
  - 5 barres verticales animées (amplitude réelle via soundLevel)
  - Hauteur barres : 8px min, 40px max
  - Ring pulsant autour du bouton (expand + fade, 1.2s)
  - Texte flottant : "Écoute en cours… (fr_MA)"
```

**Sources Bottom Sheet :**
```
DraggableScrollableSheet : 50% → 85% écran
Header : "Sources RAG" h3 + nombre de sources
─────────────────────────────────
Chaque source :
  [01]  Nom du document          ← numéro en circle gradient
        type : MedicalGuideline  ← badge surface-3 rounded
        score : 0.87             ← JetBrains Mono + progress bar
─────────────────────────────────
```

**AppBar menu ⋮ (3 points) :**
```
→ Historique des conversations
→ Nouvelle conversation
→ Effacer la conversation (DELETE /chat/{id})
```

**État : consent_nlp = false :**
```
Banner permanent en haut :
"🔒 Chat IA désactivé — Activez le consentement NLP dans votre profil"
[Activer maintenant] → navigate('/consent')
```

---

### 3.6 Conversations History (drawer/page)

**Endpoint :** `GET /chat?limit=20&offset=0`

**Layout :**
```
┌────────────────────────────┐
│ ←  Conversations       +  │  ← + = nouvelle conversation
│                            │
│ ┌────────────────────────┐ │
│ │ 💬 Douleurs thoraciques │ │  ← titre extrait du 1er message
│ │    FR · 3 messages      │ │  ← langue + nombre
│ │    il y a 2 heures      │ │  ← date relative
│ └────────────────────────┘ │
│                            │
│ ┌────────────────────────┐ │
│ │ 💬 Mon traitement...   │ │  ← swipe to delete → DELETE /chat/{id}
│ │    AR · 7 messages      │ │
│ │    hier                 │ │
│ └────────────────────────┘ │
└────────────────────────────┘
```

**Swipe left → supprimer :** confirmation dialog avant DELETE

---

### 3.7 Appointments Page (US-50)

**Endpoints :**
- `GET /predictions/no-show/batch?doctor_uuid=current&date=...`

**Layout :**
```
┌────────────────────────────┐
│  Rendez-vous           +   │  ← FAB pour nouveau RDV (stub)
│                            │
│ ┌── Date picker ─────────┐ │  ← input date, surface-2
│ │  📅  Aujourd'hui       │ │
│ └────────────────────────┘ │
│                            │
│ ┌── Résumé risque ───────┐ │
│ │  3 ●●  1 ●●  2 ●●      │ │  ← dots colorés + nombre
│ │  Faible Modéré Élevé   │ │     single card surface-1
│ └────────────────────────┘ │
│                            │
│ ─── Liste des RDVs ─────── │
│                            │
│ ┌────────────────────────┐ │
│ │ ●  09:30               │ │  ← dot gauche (risk-danger glow)
│ │    Dr. Saad Merrouni   │ │  ← nom médecin
│ │    Consultation générale│ │  ← type
│ │    [🔴 Risque élevé 67%]│ │  ← risk badge
│ └────────────────────────┘ │
│                            │
│ ┌────────────────────────┐ │
│ │ ●  11:00               │ │  ← dot vert (risk-safe glow)
│ │    Dr. Laila Bennis    │ │
│ │    Cardiologie          │ │
│ │    [🟢 Faible risque 12%]│ │
│ └────────────────────────┘ │
└────────────────────────────┘
```

**Card RDV — détail :**
```
Container surface-1
Border-left : pas de trait → DOT gauche de 10px coloré avec glow
              (box-shadow: 0 0 8px 3px <risk-color>@50%)
Padding : 16px
Row :
  [DOT] [Column : heure Clash h3 | médecin body | type small muted]
  [RISK BADGE]
```

**Risk Badge :**
```
Pill rounded-full
Background : risk-color @ 15%
Border : 1px solid risk-color @ 60%
Text : "🔴 Risque élevé · 67%" en Inter 11px risk-color
```

**État vide :**
```
Icône calendrier animée (bounce doux)
"Aucun rendez-vous pour cette date"
[Sélectionner une autre date]
```

**État : pas de prédiction (null risk_color) :**
- Dot gris, badge "Non calculé" gris muted

---

### 3.8 IoT Dashboard Page (US-49)

**Endpoint cible :** `GET /iot/metrics/{patient_uuid}?days=7` (Sprint 7)
**Actuellement :** mock data avec BiometricMockData.generate()

**Layout :**
```
┌────────────────────────────┐
│  Biométrie              ⟳  │  ← refresh button
│                            │
│ [7 jours] [30 jours] [90j] │  ← chips sélecteur (gradient = actif)
│                            │
│ ══ ÉTAT 1 : NO_DEVICE ═══ │
│  [Bluetooth icon pulsant]  │
│  "Connectez votre bracelet"│
│  [Scanner le QR code]      │
│                            │
│ ══ ÉTAT 2 : SYNCING ══════ │
│  [Spinner gradient]        │
│  "Synchronisation…"        │
│  "Dernière sync: 14h32"    │
│                            │
│ ══ ÉTAT 3 : DATA ═════════ │
│                            │
│ ┌───────┐ ┌───────┐        │  ← scroll horizontal
│ │  ❤️   │ │  🫁   │        │
│ │  72   │ │  98%  │        │  ← Clash Display 40px
│ │  BPM  │ │  SpO2 │        │  ← glow sous le chiffre
│ │ ↑Norm │ │ ✓Exc  │        │
│ └───────┘ └───────┘        │
│ ┌───────┐                  │
│ │  〰  │                  │
│ │  42ms │                  │
│ │  HRV  │                  │
│ │ ↓ Bas │                  │
│ └───────┘                  │
│                            │
│ ─ Fréquence Cardiaque ──── │
│ [LineChart gradient rouge] │  ← fl_chart, dark bg, no grid
│                            │
│ ─ SpO2 ─────────────────── │
│ [LineChart gradient bleu]  │
│                            │
│ ─ HRV ──────────────────── │
│ [LineChart gradient violet]│
│                            │
│ [dev] Données simulées     │  ← banner jaune si isDev=true
└────────────────────────────┘
```

**Metric Card — détail :**
```
surface-1, radius-xl, padding 20px
Width : 140px (horizontal scroll)

Icon : emoji dans circle surface-3 (40px)
Value : Clash Display 40px, metric.color
        + BoxShadow: 0 0 20px metric.color@40% (glow sous le chiffre)
Unit : Inter 12px text-muted
Trend : ↑ risk-safe | ↓ risk-danger | → text-muted
Status text : "Normal" / "Excellent" / "Bas" en Inter 11px
```

**Graphiques :**
```
LineChart fl_chart :
  bg : transparent (sur surface-0)
  Grille : fines lignes surface-2 horizontales seulement
  Ligne : gradient stroke (color @ 100% → color @ 20%)
  Fill : gradient sous la ligne (color @ 8% → transparent)
  Pas de dots sur la ligne
  isCurved : true
  Tooltip : dark card avec valeur + timestamp
```

---

### 3.9 Profile Page (US-59 + RGPD)

**Endpoints :**
- `GET /auth/me` → données utilisateur
- `POST /patient/consent` → mise à jour consentement
- `GET /patients/{uuid}/data/export` → export RGPD
- `DELETE /patients/{uuid}` → droit à l'oubli
- `POST /auth/logout`

**Layout :**
```
┌────────────────────────────┐
│  Profil                    │
│                            │
│ ┌── HEADER ──────────────┐ │
│ │  [mesh gradient bg]    │ │  ← blobs flous indigo+violet
│ │       [A]              │ │  ← Avatar circle, border gradient 3px
│ │   Ahmed Benali         │ │  ← Clash Display 24px
│ │   [patient]            │ │  ← pill surface-2, border gradient 1px
│ │   ahmed@email.com      │ │  ← text-muted
│ └────────────────────────┘ │
│                            │
│ SANTÉ & DONNÉES            │  ← section label CAPS 11px text-muted
│ ┌────────────────────────┐ │
│ │ 🔔  Rappels médicaments│→│  ← chevron
│ │     Gérer vos rappels  │ │
│ └────────────────────────┘ │
│ ┌────────────────────────┐ │
│ │ ⬇  Exporter mes données│→│
│ │     Art. 20 RGPD       │ │
│ └────────────────────────┘ │
│                            │
│ CONFIDENTIALITÉ            │
│ ┌────────────────────────┐ │
│ │ 🔒  Mes consentements  │→│
│ │     IoT · NLP · Partage│ │
│ └────────────────────────┘ │
│ ┌────────────────────────┐ │
│ │ 🗑  Effacer mes données │ │  ← DESTRUCTIF: rouge
│ │     Art. 17 RGPD       │ │
│ └────────────────────────┘ │
│                            │
│ COMPTE                     │
│ ┌────────────────────────┐ │
│ │ →  Se déconnecter      │ │
│ └────────────────────────┘ │
│                            │
│  v1.0.0 · EMSI Marrakech   │  ← micro centered
└────────────────────────────┘
```

**Export RGPD :**
```
Dialog de confirmation :
  Titre : "Exporter vos données"
  Corps : "Vous recevrez un fichier JSON contenant vos données
           de santé, historique de consentement et logs d'accès."
  [Annuler] [Télécharger]
→ Download du fichier JSON
```

**Effacement (Droit à l'oubli) :**
```
Dialog double confirmation :
  Étape 1 : "Êtes-vous sûr ? Cette action est irréversible."
             [Annuler] [Continuer]
  Étape 2 : "Tapez EFFACER pour confirmer"
             TextField → bouton actif seulement si text = "EFFACER"
→ DELETE /patients/{uuid}
→ Logout + navigate('/login')
→ SnackBar : "Vos données ont été effacées (Art. 17 RGPD)"
```

---

### 3.10 Medication Reminders Page (US-59)

**Endpoint :** aucun (stockage local, notifications flutter_local_notifications)

**Layout :**
```
┌────────────────────────────┐
│ ←  Rappels médicaments  +  │  ← + ajouter un rappel
│                            │
│ ┌────────────────────────┐ │
│ │ 💊  Metformine 500mg   │ │
│ │     1 comprimé matin   │ │
│ │     ⏰ 08:00           │ │  ← heure du rappel
│ │                  [ON]  │ │  ← toggle
│ └────────────────────────┘ │
│                            │
│ ┌────────────────────────┐ │
│ │ 💊  Aspirine 100mg     │ │
│ │     1/2 comprimé soir  │ │
│ │     ⏰ 21:00           │ │
│ │                 [OFF]  │ │
│ └────────────────────────┘ │
│                            │
│  Swipe left → supprimer    │  ← swipe action
└────────────────────────────┘
```

**Ajouter un rappel (bottom sheet) :**
```
TextField : Nom du médicament
TextField : Dosage/instructions
TimePicker : Heure
Toggle : Activer
[Enregistrer]
```

---

## 4. Dashboard Web Next.js — Médecin

### 4.0 Navigation globale

```
[/login] ──→ role=doctor ──→ [/agenda]
                                ↓
                          [/patients/{uuid}/dpa]
                                ↓
                    [/patients/{uuid}/dpa/action/{id}]
```

---

### 4.1 Layout Commun (sidebar)

```
┌──────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────┐  │
│ │          │ │                                │  │
│ │  SIDEBAR │ │     CONTENU PRINCIPAL          │  │
│ │ 240px    │ │                                │  │
│ │          │ │                                │  │
│ │ MediSense│ │                                │  │
│ │    AI    │ │                                │  │
│ │          │ │                                │  │
│ │──────────│ │                                │  │
│ │ Agenda   │ │                                │  │
│ │ Patients │ │  (scrollable)                  │  │
│ │          │ │                                │  │
│ │──────────│ │                                │  │
│ │ [avatar] │ │                                │  │
│ │ Dr. Smoke│ │                                │  │
│ │ doctor   │ │                                │  │
│ │ [logout] │ │                                │  │
│ └──────────┘ └────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
Background global : surface-0
Sidebar bg : surface-1, border-right 1px surface-2
```

**Sidebar nav items :**
```
Lien actif   : bg surface-2, border-left 3px gradient AI, text-primary
Lien hover   : bg surface-2 @ 50%
Lien normal  : text-secondary
Icon : 20px, même couleur que texte
```

---

### 4.2 Login Page (US-51)

**Endpoint :** `POST /auth/login`

```
┌────────────────────────────────────────────────────┐
│                                                    │
│             ≋≋≋  MediSense AI                     │  ← waveform + titre
│        Tableau de bord clinique                    │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │                                              │  │  ← card surface-1
│  │  Connexion                                   │  │     shadow card-shadow
│  │                                              │  │
│  │  Email professionnel                         │  │
│  │  ┌──────────────────────────────────────┐   │  │
│  │  │  medecin@clinique.ma                 │   │  │
│  │  └──────────────────────────────────────┘   │  │
│  │                                              │  │
│  │  Mot de passe                                │  │
│  │  ┌─────────────────────────────── 👁 ──┐   │  │
│  │  │  ••••••••••••••••••••              │   │  │
│  │  └──────────────────────────────────────┘   │  │
│  │                                              │  │
│  │  [Erreur si présente]                        │  │
│  │                                              │  │
│  │  ┌──────────────────────────────────────┐   │  │
│  │  │         Se connecter                 │   │  │  ← gradient button
│  │  └──────────────────────────────────────┘   │  │
│  │                                              │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│    MediSense AI · n.synergy · EMSI Marrakech       │
└────────────────────────────────────────────────────┘
Background : surface-0
```

**Redirect post-login :**
```
role = doctor    → /agenda
role = secretary → /agenda
role = admin     → /admin/audit-logs
```

---

### 4.3 Agenda Intelligent (US-53)

**Endpoints :**
- `GET /predictions/no-show/batch?doctor_uuid=current&date=...`
- `POST /predictions/no-show/reminders/dispatch`

```
┌────────────────────────────────────────────────────┐
│ Agenda Intelligent                                 │
│ Prédiction no-show · XGBoost v2.1                 │
│                                                    │
│ ┌─────────────────────────────────────────────┐   │
│ │ [📅 2026-05-10] [↺ Actualiser] [📨 SMS risk]│   │  ← toolbar
│ └─────────────────────────────────────────────┘   │
│                                                    │
│ ┌──────────────┬──────────────┬──────────────┐    │  ← 3 stat cards
│ │   3          │   1          │   2           │    │     surface-1
│ │   ● Faible   │   ● Modéré   │   ● Élevé     │    │     chiffre Clash h1
│ └──────────────┴──────────────┴──────────────┘    │     couleur = risk-color
│                                                    │     glow si >0
│ ┌─────────────────────────────────────────────┐   │
│ │ Heure  │ Patient     │ No-show │ Statut │SMS│   │  ← thead surface-2
│ ├─────────────────────────────────────────────┤   │
│ │ 09:30  │ a1b2c3d4…   │ 🔴 67%  │pending │ 0 │   │
│ │ 10:00  │ e5f6g7h8…   │ 🟡 34%  │confirm │ 1 │   │
│ │ 11:00  │ i9j0k1l2…   │ 🟢 8%   │pending │ 0 │   │
│ └─────────────────────────────────────────────┘   │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Colonne No-show :**
```
Risk badge :
  bg : risk-color @ 10%
  border : 1px risk-color @ 50%
  text : risk-color
  format : "🔴 67%" ou "⚠ 34%" ou "✓ 8%"
```

**Bouton "Envoyer rappels SMS" :**
```
Gradient button (ai-from→ai-to)
État : pending → affiche "Envoi…" + spinner
Résultat : toast "12 SMS envoyés · 3 ignorés"
Toast position : top-right, surface-1, border risk-safe, 3s auto-dismiss
```

**Ligne cliquable :**
- Clic sur une ligne → navigate vers `/patients/{patient_uuid}/dpa`

---

### 4.4 DPA — 3 Colonnes (US-52)

**Endpoints :**
- `GET /doctor/patient/{uuid}/dpa-summary`
- `POST /doctor/dpa-summary/{id}/approve`
- `POST /doctor/dpa-summary/{id}/reject`
- `PATCH /doctor/dpa-summary/{id}/action/{action_id}`

```
┌────────────────────────────────────────────────────────┐
│ ← Retour à l'agenda                                    │
│                                                        │
│ Résumé DPA            [● PENDING]  ↺ il y a 5 min    │
│ Patient: a1b2c3d4…    Confiance : ██████░ 78%         │
│                                                        │
│ ┌──────────────┬──────────────┬──────────────────────┐ │
│ │ SYMPTÔMES    │ BIOMÉTRIE    │ ACTIONS IA            │ │
│ │ (RAG Sprint3)│ (IoT Sprint7)│ (XGBoost Sprint5)     │ │
│ ├──────────────┼──────────────┼──────────────────────┤ │
│ │ • Douleurs   │ Tendance ↓   │ ┌──────────────────┐ │ │
│ │   thoraciques│              │ │ PRESCRIRE        │ │ │
│ │              │ [CRITIQUE]   │ │ Metformine 500mg │ │ │
│ │ • Essouf-    │ SpO2: 91%    │ │ [████░░] 85%     │ │ │
│ │   flement    │ < seuil 95%  │ │ [✓] [✗] [✏]     │ │ │
│ │              │ il y a 2h    │ └──────────────────┘ │ │
│ │ • Toux       │              │                      │ │
│ │   persistante│ [MODÉRÉ]     │ ┌──────────────────┐ │ │
│ │              │ HRV: 28ms    │ │ RÉFÉRER          │ │ │
│ │              │ < seuil 35ms │ │ Cardiologue      │ │ │
│ │              │              │ │ [███░░░] 62%     │ │ │
│ │              │ Aucune autre │ │ [✓] [✗] [✏]     │ │ │
│ │              │ anomalie     │ └──────────────────┘ │ │
│ └──────────────┴──────────────┴──────────────────────┘ │
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ✏ Note du médecin (optionnel)                      │ │
│ │ ┌──────────────────────────────────────────────┐   │ │
│ │ │ Ajoutez vos observations…                    │   │ │
│ │ └──────────────────────────────────────────────┘   │ │
│ │ [✓ Valider le résumé]  [✗ Rejeter]                 │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

**Statut badge :**
```
PENDING  : bg amber@10%, border amber, text amber  — pulsing dot
APPROVED : bg green@10%, border green, text green  — static dot
MODIFIED : bg blue@10%, border blue, text blue     — static dot
REJECTED : bg red@10%, border red, text red        — static dot
```

**Barre de confiance globale :**
```
label "Confiance : 78%"
bg : surface-3, radius-full, h-2
fill : gradient ai-from→ai-to @ width% (animated on mount 0→78%)
couleur du % : confiance ≥80% vert | 60-79% indigo | <60% orange | <40% rouge
```

**Action Card (dans Col 3) :**
```
surface-1, rounded-xl, padding 16px, border 1px surface-2

Header row :
  type tag (PRESCRIRE/RÉFÉRER/MONITORER/ALERTER)
    → couleur par type (blue/purple/amber/red)
  confiance barre mini + pourcentage JetBrains Mono

Description : body-sm
Rationale : small text-muted italic

─── Action buttons ────────────────────
[✓] Approuver    → bg risk-safe@10%, border risk-safe, 28px icon button
[✗] Rejeter      → bg risk-danger@10%, border risk-danger
[✏] Modifier     → bg surface-3, border surface-2 → ouvre dialog d'édition

État approuvée : fond risk-safe@5%, checkmark vert overlay
État rejetée   : fond risk-danger@5%, croix rouge, texte barré
```

**Reject Modal :**
```
Dialog centré, surface-1, rounded-2xl, shadow xl
Titre : "Motif de rejet" h3
Textarea : minimum 10 caractères (compteur affiché)
Compteur : "4/10" en mono rouge si <10, vert si ≥10
[Annuler] [Confirmer le rejet] ← désactivé si <10 chars

Sur succès → badge REJECTED + invalidate query
```

**Conflit (409 Optimistic Lock) :**
```
Toast erreur :
"Ce résumé a déjà été traité par un autre médecin.
 Rechargement en cours…"
→ refetch automatique
```

---

## 5. Dashboard Web Next.js — Secrétaire

### 5.0 Navigation

```
[/login] → role=secretary → [/agenda]
                                ↓
                          [/crm/tasks]
```

### 5.1 Agenda (secrétaire)

**Mêmes endpoints que médecin + `POST /predict/feedback`**

Différence principale : **bouton "Feedback ML" par RDV**

```
Colonne supplémentaire dans le tableau :
│ Statut réel  │
│ [COMPLETED ▾]│  ← dropdown : COMPLETED / NO_SHOW
│ [Soumettre]  │  → POST /predict/feedback
```

**Dialog Feedback ML :**
```
"Confirmer le résultat du rendez-vous"
Patient : a1b2c3d4…
RDV prévu : 09:30 — 10 mai 2026
Résultat :
  ○ Présenté (COMPLETED)
  ● Absent (NO_SHOW)
Commentaire médecin (optionnel) : TextField
[Annuler] [Soumettre le feedback]
```

---

### 5.2 CRM Tasks Page (US-43)

**Endpoints :**
- `GET /crm/tasks?crm_sync_status=...&limit=50`
- `PATCH /crm/tasks/{uuid}`
- `POST /crm/tasks/{uuid}/retry`

```
┌────────────────────────────────────────────────────┐
│ Tâches CRM Salesforce                              │
│ Synchronisation automatique · Sprint 6             │
│                                                    │
│ Filtre : [Tous ▾] [PENDING ▾]  [↺ Actualiser]    │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Patient    │ Heure  │ Statut CRM │ Erreur │ ↺ │  │
│ ├──────────────────────────────────────────────┤  │
│ │ a1b2c3…   │ 09:30  │ ● SENT     │   —    │   │  │
│ │ e5f6g7…   │ 10:00  │ ● FAILED   │ Timeout│ ↺ │  │  ← retry btn
│ │ i9j0k1…   │ 11:00  │ ● PENDING  │   —    │   │  │
│ │ m2n3o4…   │ 14:00  │ ● CB_OPEN  │ CB Err │ ↺ │  │  ← circuit breaker
│ └──────────────────────────────────────────────┘  │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Statut CRM badges :**
```
PENDING  : amber pill  "● En attente"
SENT     : green pill  "● Synchronisé"
FAILED   : red pill    "● Échec"
SKIPPED  : gray pill   "○ Ignoré"
CB_OPEN  : red pill + ⚡ "⚡ Circuit ouvert"
```

**Bouton retry :**
- Visible seulement pour FAILED et CB_OPEN
- `POST /crm/tasks/{uuid}/retry` → badge passe à PENDING + spinner
- Erreur si max retries atteint → toast "Nombre maximum de tentatives atteint"

---

## 6. Dashboard Web Next.js — Admin

### 6.0 Navigation

```
[/login] → role=admin → [/admin/audit-logs]
                              ↓
                        [/admin/users]
                              ↓
                        [/admin/system] (rerank-eval)
```

---

### 6.1 Audit Logs RGPD (US-60)

**Endpoint :** `GET /admin/audit-logs?limit=20&offset=...`

```
┌────────────────────────────────────────────────────┐
│ Logs d'Audit RGPD                                  │
│ Journal immuable · Art. 30 RGPD · 4 821 entrées   │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ [Action ▾]  [Rôle ▾]  [Date]  [Chercher UUID]│  │  ← filtres
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │Horodatage│Action  │Rôle   │Ressource│IP      │  │
│ ├──────────────────────────────────────────────┤  │
│ │10/05 14:32│[LOGIN] │admin  │user     │127.0.1 │  │
│ │10/05 14:28│[EXPORT]│admin  │patient  │127.0.1 │  │
│ │10/05 11:15│[DELETE]│admin  │patient  │127.0.1 │  │
│ │10/05 09:00│[CONSENT│patient│patient  │10.0.2.2│  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
│ Page 1 / 241   [◀]                    [▶]         │  ← pagination
└────────────────────────────────────────────────────┘
```

**Action color badges :**
```
LOGIN   : bg blue@10%,   border blue,   "● LOGIN"
READ    : bg slate@10%,  border slate,  "○ READ"
WRITE   : bg green@10%,  border green,  "● WRITE"
DELETE  : bg red@10%,    border red,    "✕ DELETE"
EXPORT  : bg purple@10%, border purple, "↓ EXPORT"
CONSENT : bg amber@10%,  border amber,  "⚙ CONSENT"
```

**Expandable row :** clic sur une ligne → révèle user_agent complet, resource_uuid complet

---

### 6.2 Users Management (US-60 stub)

**Endpoint :** aucun pour l'instant (Sprint 10 US-60 partiel)

```
┌────────────────────────────────────────────────────┐
│ Gestion des Utilisateurs                           │
│ Création et désactivation des comptes staff        │
│                                                    │
│ [+ Créer un compte]                                │  ← modal à implémenter
│                                                    │
│ ┌──────────────────────────────────────────────┐  │
│ │ Email                │ Rôle     │ Statut │ ⋮ │  │
│ ├──────────────────────────────────────────────┤  │
│ │ admin@medisense.ai   │ admin    │ ✓ Actif│   │  │
│ │ smoke@medisense.ma   │ doctor   │ ✓ Actif│   │  │
│ │ patient@medisense.ai │ patient  │ ✓ Actif│   │  │
│ └──────────────────────────────────────────────┘  │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Menu ⋮ par utilisateur :**
```
→ Désactiver le compte
→ Réinitialiser le mot de passe
→ Voir les logs d'audit
```

---

### 6.3 Rerank Evaluation (US-12 — Admin seulement)

**Endpoint :** `POST /admin/rerank-eval`

```
┌────────────────────────────────────────────────────┐
│ Évaluation RAG — RRF vs Cross-Encoder              │
│ Diagnostic qualité de la recherche vectorielle     │
│                                                    │
│ Requête de test :                                  │
│ ┌──────────────────────────────────────────────┐  │
│ │ douleurs thoraciques insuffisance cardiaque  │  │
│ └──────────────────────────────────────────────┘  │
│ Top-K : [10 ▾]                                    │
│ [▶ Lancer l'évaluation]                           │
│                                                    │
│ ─── Résultats ──────────────────────────────────  │
│                                                    │
│ Rank Correlation : 0.87    ← Spearman ρ            │
│ Top-3 Overlap    : 2/3                             │
│ MRR (RRF)        : 0.82                            │
│                                                    │
│ ┌─────────────────┬──────────────────────────┐    │
│ │ RRF Top-3       │ Cross-Encoder Top-3       │    │
│ ├─────────────────┼──────────────────────────┤    │
│ │ 1. Cardio guide │ 1. Cardio guide (0.94)   │    │
│ │ 2. ECG protocol │ 2. ECG protocol (0.91)   │    │
│ │ 3. Chest pain   │ 3. HF guidelines (0.87)  │    │
│ └─────────────────┴──────────────────────────┘    │
└────────────────────────────────────────────────────┘
```

---

## 7. Composants partagés

### GradientButton
```
Props : label, onPressed, isLoading, width (full | auto)

Normal   : LinearGradient(ai-from→ai-to), text white Clash Display
Loading  : spinner blanc centré, opacity 0.7
Disabled : surface-3, text-muted
Radius   : rounded-full (Flutter) / rounded-full (Next.js)
Height   : 52px (Flutter), 48px (Next.js)
```

### RiskBadge
```
Props : riskColor (green/orange/red/null), probability (0.0–1.0)

Pill rounded-full, px 10px py 4px
bg : risk-color @ 12%
border : 1px solid risk-color @ 50%
text : risk-color, Inter 11px bold
format : "● 67%" ou "✓ 8%" ou "⚠ 34%"
null → "○ —" gris muted
```

### ConfidenceBar
```
Props : value (0.0–1.0)

label "Confiance · 78%" Inter 12px
bar : h-1.5, bg surface-3, radius-full
fill : gradient ai-from→ai-to, width = value*100%
       animation : width 0→target en 800ms (ease-out)
```

### StatusBadge (DPA)
```
PENDING  : amber pulsing dot + "En attente"
APPROVED : green static dot + "Approuvé"
MODIFIED : blue static dot + "Modifié"
REJECTED : red static dot + "Rejeté"
```

### AuditActionBadge
```
Par action : couleur + icône + label
Pill surface@10%, border 1px, text colored
```

### AIWaveform
```
5 barres verticales, gap 3px
Hauteur : [12, 24, 40, 24, 12]px en repos
Animation idle : staggered sine wave (200ms offset entre barres)
Animation active (streaming) : amplitude aléatoire 8–48px, 60fps
Couleur : ai-from (#6366F1)
```

---

## 8. États universels

### Chaque liste / page doit gérer :

```
┌─────────────────────────────────────────────┐
│ LOADING                                     │
│   Skeleton cards (surface-2 shimmer effect) │
│   Shimmer : gradient surface-2→surface-3    │
│              animé left→right, 1.5s loop    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ EMPTY                                       │
│   Icône thématique (48px, text-muted)       │
│   Titre : "Aucun [élément] trouvé" h3       │
│   Sous-titre : contexte actionnable         │
│   [CTA optionnel]                           │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ERROR                                       │
│   Icône ⚠ (48px, risk-danger)              │
│   "Une erreur est survenue"                 │
│   Message d'erreur technique (text-muted)   │
│   [↺ Réessayer]                             │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ NO_CONSENT (chat uniquement)                │
│   Icône 🔒 (48px, text-muted)              │
│   "Chat IA désactivé"                       │
│   [Activer le consentement NLP →]           │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ UNAUTHORIZED (Next.js)                      │
│   Redirection automatique vers /login       │
│   + toast "Session expirée, reconnectez-vous│
└─────────────────────────────────────────────┘
```

---

## 9. Motion & Animation

### Règles de durée

```
Micro (hover, toggle)    : 100–150ms  ease-out
Transitions page         : 300ms      ease-in-out
Apparition d'éléments    : 200–250ms  spring (k=200, d=25)
Animations données       : 600–800ms  ease-out
Animations d'attente     : loop       linear
```

### Animations par écran

| Écran | Élément | Animation |
|-------|---------|-----------|
| Splash | Waveform barres | Staggered sine, 400ms each |
| Login | Focus input | Bottom border grows left→right, 200ms |
| Login | Error | Shake X ±8px, 3 oscillations, 150ms |
| Chat | Bulle apparition | Scale 0.85→1.0 + fadeIn, 200ms, spring |
| Chat | Streaming border | Traveling light up→down, 1.5s loop |
| Chat | Voice recording | Waveform amplitude-driven, realtime |
| Chat | Urgency banner | SlideDown 400ms + pulse icon 1.5s loop |
| IoT | Metric value | Count-up 0→value, 1000ms ease-out |
| IoT | Chart | Draw line left→right, 800ms ease-out |
| IoT | Glow | Pulse 1.0→1.3→1.0 opacity, 2s loop |
| DPA | Confidence bar | Width 0%→value, 800ms ease-out |
| DPA | Action approved | CheckCircle scale 0→1, green flash |
| DPA | Action rejected | X scale 0→1, text strikethrough |
| Agenda | Risk badge appear | Scale 0→1 spring, 400ms |

---

## 10. Accessibilité & RGPD by Design

### Accessibilité

```
Contraste minimum : 4.5:1 (texte normal), 3:1 (large)
  surface-0 + text-primary  : ✅ 18.5:1
  surface-1 + text-secondary: ✅ 7.2:1
  surface-2 + text-muted    : ✅ 4.6:1

Touch targets : minimum 48×48px (toutes les actions)
Fonts : scalables (textScaleFactor Flutter, rem Next.js)
Focus visible : ring gradient 2px offset sur tous les éléments focusables
Labels ARIA : tous les boutons icônes ont aria-label
RTL support : miroir pour arabe (layout Flutter + CSS direction:rtl)
```

### RGPD dans l'UI

```
Chaque action sensible RGPD affiche :
  → L'article de loi applicable
  → Une description en langage simple
  → Une confirmation double pour les actions irréversibles

Signaux visuels RGPD :
  🔒 = données chiffrées
  📋 = auditée dans les logs
  ⚠ = irréversible
  🕐 = horodatage affiché

Données affichées :
  UUIDs : tronqués à 8 chars + "…" (jamais complets en UI)
  Dates : formatées en locale (fr-MA)
  Confiance IA : TOUJOURS affichée (AI Act Art. 13)
```

---

## Récapitulatif — Chaîne complète par rôle

```
PATIENT (Flutter) :
Splash → Onboarding → Login → Consent → Chat (stream SSE)
  → Conversations History → Sources BottomSheet
  → Appointments (risk colors) → IoT Dashboard (charts)
  → Profile → Reminders | Export | Consent update | Erasure

MÉDECIN (Next.js) :
Login → Agenda (risk table + SMS dispatch)
  → DPA 3-col (symptômes + IoT + actions)
    → Approve global | Reject (note obligatoire)
    → Approve/Reject/Edit individual action

SECRÉTAIRE (Next.js) :
Login → Agenda (+ feedback ML par RDV)
  → CRM Tasks (statuts Salesforce + retry)

ADMIN (Next.js) :
Login → Audit Logs (filtres + pagination)
  → Users (activation/désactivation)
  → Rerank Eval (diagnostic RAG)
  → Toutes les actions médecin + secrétaire
```
