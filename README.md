# 🎯 Veille emploi automatique — Adrien Lucas

Ce projet récupère **chaque jour automatiquement** les nouvelles offres
d'emploi correspondant à ton profil (SDR/BDR, Account Executive, Account
Manager — SaaS/B2B) à Paris, Lyon, Nantes et en full remote, via l'API
officielle **France Travail**, et génère une page web ("dashboard") que tu
peux consulter depuis ton téléphone ou ton ordinateur.

Aucune donnée personnelle n'est utilisée : seules les offres d'emploi
publiques sont interrogées.

---

## Comment ça marche

```
Chaque jour à 7h (heure de Paris)
        │
        ▼
GitHub Actions réveille le script
        │
        ▼
Le script interroge l'API France Travail
(plusieurs recherches × plusieurs villes)
        │
        ▼
Filtrage : nouvelles offres uniquement,
score de pertinence, exclusions
        │
        ▼
Génération d'une page HTML (dashboard)
        │
        ▼
Publication automatique sur GitHub Pages
→ ton lien personnel, mis à jour chaque jour
```

---

## Installation (15-20 minutes, une seule fois)

### Étape 1 — Crée un compte sur l'API France Travail

1. Va sur **https://francetravail.io/**
2. Crée un compte développeur (gratuit)
3. Une fois connecté, va dans **"Mes applications"** → **"Créer une application"**
4. Donne-lui un nom (ex: `veille-emploi-adrien`)
5. Dans les API à associer, coche **"Offres d'emploi v2"**
6. Une fois créée, note bien ton **Identifiant client (Client ID)** et ton
   **Secret client (Client Secret)** — tu en auras besoin à l'étape 3.

> ⚠️ Garde ces identifiants secrets, ne les partage jamais publiquement
> (ne les mets jamais directement dans le code).

### Étape 2 — Crée le dépôt GitHub

1. Va sur **https://github.com/new**
2. Nom du dépôt : `veille-emploi` (ou ce que tu veux)
3. Visibilité : **Privé** (recommandé, pour ne pas exposer publiquement ton CV/profil) ou Public, comme tu préfères
4. Ne coche aucune case d'initialisation (pas de README, pas de .gitignore — on a déjà tout)
5. Clique sur **"Create repository"**

Ensuite, sur ton ordinateur, dans un terminal :

```bash
cd chemin/vers/le/dossier/job-alert
git init
git add .
git commit -m "Premier import du projet de veille emploi"
git branch -M main
git remote add origin https://github.com/TON-NOM-UTILISATEUR/veille-emploi.git
git push -u origin main
```

(Remplace `TON-NOM-UTILISATEUR` par ton pseudo GitHub.)

### Étape 3 — Configure les secrets sur GitHub

C'est ici que tu donnes au script l'accès à l'API, **sans jamais exposer tes
identifiants** dans le code.

1. Sur la page de ton dépôt GitHub, va dans **Settings** (Paramètres)
2. Dans le menu de gauche : **Secrets and variables** → **Actions**
3. Clique sur **"New repository secret"**
4. Crée un premier secret :
   - Nom : `FT_CLIENT_ID`
   - Valeur : ton Client ID de l'étape 1
5. Crée un second secret :
   - Nom : `FT_CLIENT_SECRET`
   - Valeur : ton Client Secret de l'étape 1

### Étape 4 — Active GitHub Pages

1. Toujours dans **Settings** → **Pages** (menu de gauche)
2. Sous "Build and deployment" → "Source", choisis **"GitHub Actions"**
3. Sauvegarde

### Étape 5 — Lance le premier test manuel

1. Va dans l'onglet **Actions** de ton dépôt
2. Clique sur le workflow **"Veille emploi quotidienne"**
3. Clique sur **"Run workflow"** → **"Run workflow"** (bouton vert)
4. Attends 1-2 minutes, rafraîchis la page : tu dois voir une coche verte ✅

Si tu vois une croix rouge ❌, clique sur le run pour voir le détail de
l'erreur (souvent : secrets mal nommés, ou une faute de frappe dans le Client
ID/Secret).

### Étape 6 — Récupère ton lien

1. Dans **Settings** → **Pages**, ton URL apparaît en haut, du type :
   `https://ton-nom-utilisateur.github.io/veille-emploi/`
2. Mets ce lien en favori sur ton téléphone — c'est ton dashboard quotidien !

---

## Personnaliser ta recherche

Tout se règle dans **`config/profil.json`** — pas besoin de toucher au code.

```json
{
  "recherches": [
    { "nom": "SDR / BDR", "motsCles": "SDR business developer prospection commerciale" }
  ],
  "villes": [
    { "nom": "Paris", "codeInsee": "75056", "rayonKm": 15 }
  ],
  "mots_cles_exclus": ["stage", "alternance"]
}
```

- **Ajouter un métier recherché** : ajoute un objet dans `recherches`
- **Ajouter une ville** : ajoute un objet dans `villes` (le code INSEE se
  trouve facilement en recherchant "code INSEE [nom de ville]")
- **Exclure des mots** : ajoute-les dans `mots_cles_exclus`

Après modification, commit et push le fichier — le prochain run l'utilisera
automatiquement :

```bash
git add config/profil.json
git commit -m "Ajuste les critères de recherche"
git push
```

---

## Comment lire le dashboard

- Chaque **carte** = une offre
- **Pastille de couleur** = score de correspondance avec ton profil
  (mots-clés de ton CV détectés dans l'offre) :
  - 🔴 **Lead chaud** : forte correspondance
  - 🟡 **À qualifier** : correspondance partielle
  - ⚪ **Découverte** : correspond aux critères de base, à regarder rapidement
- Les jours précédents restent visibles (historique sur 14 jours), repliés
  par défaut — clique pour dérouler.

---

## Limites à connaître

- Le **scoring** est un indicateur basé sur la présence de mots-clés dans
  l'offre, pas une analyse fine — un poste mal noté peut quand même être
  intéressant, regarde toujours le titre et l'entreprise.
- L'API France Travail couvre une **large partie** du marché français mais
  pas 100% des offres (certaines plateformes type LinkedIn ne partagent pas
  toujours leurs offres avec l'API publique).
- Le déclenchement à 7h peut varier de quelques minutes selon la charge des
  serveurs GitHub — c'est normal.

## Pour aller plus loin (non inclus, à la demande)

- Envoi par email chaque matin
- Notification push sur téléphone
- Ajout d'autres sources (Adzuna, Welcome to the Jungle, etc.)
- Détection plus fine via une IA (par ex. en utilisant l'API Claude pour
  juger la pertinence réelle de chaque offre par rapport à ton CV)

Dis-moi si tu veux qu'on ajoute l'une de ces briques.
