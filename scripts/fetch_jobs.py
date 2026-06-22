#!/usr/bin/env python3
"""
Job Alert - Adrien Lucas
Récupère chaque jour les nouvelles offres d'emploi correspondant au profil,
via l'API officielle France Travail, et génère un dashboard HTML.

Usage:
    python3 fetch_jobs.py

Variables d'environnement requises (secrets GitHub Actions ou .env local):
    FT_CLIENT_ID      - Identifiant client API France Travail
    FT_CLIENT_SECRET  - Secret client API France Travail
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration & chemins
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "profil.json"
DATA_DIR = ROOT_DIR / "data"
SEEN_OFFERS_PATH = DATA_DIR / "offres_vues.json"
DOCS_DIR = ROOT_DIR / "docs"
HTML_OUTPUT_PATH = DOCS_DIR / "index.html"
HISTORY_PATH = DATA_DIR / "historique.json"

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
FT_API_BASE = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
FT_SCOPE = "api_offresdemploiv2 o2dsoffre"

MAX_OFFERS_PER_REQUEST = 150  # limite raisonnable par recherche/ville
REQUEST_TIMEOUT = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("job-alert")


# ---------------------------------------------------------------------------
# Authentification OAuth2
# ---------------------------------------------------------------------------

def get_access_token() -> str:
    """Récupère un token OAuth2 auprès de France Travail (valide ~20 min)."""
    client_id = os.environ.get("FT_CLIENT_ID")
    client_secret = os.environ.get("FT_CLIENT_SECRET")

    if not client_id or not client_secret:
        log.error(
            "FT_CLIENT_ID / FT_CLIENT_SECRET manquants. "
            "Configure-les en variables d'environnement (voir README)."
        )
        sys.exit(1)

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": FT_SCOPE,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    resp = requests.post(FT_TOKEN_URL, data=payload, headers=headers, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        log.error("Echec authentification France Travail: %s - %s", resp.status_code, resp.text)
        sys.exit(1)

    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Chargement config / état
# ---------------------------------------------------------------------------

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_seen_offers() -> set:
    if SEEN_OFFERS_PATH.exists():
        with open(SEEN_OFFERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ids", []))
    return set()


def save_seen_offers(ids: set) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # On garde un historique glissant pour ne pas faire grossir le fichier indéfiniment
    # (les offres France Travail expirent de toute façon après ~60 jours en général)
    with open(SEEN_OFFERS_PATH, "w", encoding="utf-8") as f:
        json.dump({"ids": list(ids), "updated_at": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Appel API France Travail
# ---------------------------------------------------------------------------

def search_offers(token: str, mots_cles: str, departement: str | None,
                   experience_codes: list[str], types_contrat: list[str]) -> list[dict]:
    """Interroge l'API offres d'emploi pour une recherche donnée."""
    headers = {"Authorization": f"Bearer {token}"}

    # minCreationDate/maxCreationDate: l'API exige les deux ensemble si on filtre par date.
    # On veut les offres publiées dans les dernières 48h (marge de sécurité).
    max_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    min_date = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "motsCles": mots_cles,
        "minCreationDate": min_date,
        "maxCreationDate": max_date,
        "sort": "1",  # tri par date, plus récent d'abord
        "range": f"0-{MAX_OFFERS_PER_REQUEST - 1}",
    }
    # On utilise le département plutôt que commune+distance: format sans ambiguïté
    # (2 chiffres), alors que certains codes commune à arrondissements (Marseille,
    # Lyon, Paris) sont parfois rejetés par cette API selon le format exact attendu.
    if departement:
        params["departement"] = departement
    if experience_codes:
        params["experience"] = ",".join(experience_codes)
    if types_contrat:
        params["typeContrat"] = ",".join(types_contrat)

    resp = requests.get(FT_API_BASE, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    # L'API renvoie 206 (Partial Content) quand il y a des résultats paginés - c'est normal
    if resp.status_code not in (200, 206):
        log.warning("Requête échouée (%s) pour '%s': %s", resp.status_code, mots_cles, resp.text[:300])
        return []

    try:
        data = resp.json()
    except ValueError:
        log.warning("Réponse non-JSON pour '%s'", mots_cles)
        return []

    return data.get("resultats", [])


def offer_mentions_remote(offer: dict, remote_keywords: list[str]) -> bool:
    text = " ".join([
        offer.get("intitule", ""),
        offer.get("description", ""),
    ]).lower()
    return any(kw.lower() in text for kw in remote_keywords)


def score_offer(offer: dict, bonus_keywords: list[str]) -> int:
    """Score simple basé sur la présence de mots-clés bonus issus du profil."""
    text = " ".join([
        offer.get("intitule", ""),
        offer.get("description", ""),
    ]).lower()
    return sum(1 for kw in bonus_keywords if kw.lower() in text)


def offer_is_excluded(offer: dict, excluded_keywords: list[str]) -> bool:
    text = " ".join([
        offer.get("intitule", ""),
        offer.get("description", ""),
    ]).lower()
    return any(kw.lower() in text for kw in excluded_keywords)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def collect_new_offers(config: dict, token: str, seen_ids: set) -> list[dict]:
    all_offers: dict[str, dict] = {}  # dédup par id

    recherches = config["recherches"]
    villes = config["villes"]
    filtres = config["filtres"]
    remote_keywords = config.get("mots_cles_remote", [])
    inclure_remote = config.get("inclure_full_remote", True)

    experience_codes = filtres.get("experience_codes_api", [])
    types_contrat = filtres.get("typeContrat", [])

    for recherche in recherches:
        mots_cles = recherche["motsCles"]
        label = recherche["nom"]

        # Recherche géolocalisée par ville (en fait, par département)
        for ville in villes:
            log.info("Recherche '%s' à %s (dept %s)...", label, ville["nom"], ville["departement"])
            offres = search_offers(
                token, mots_cles,
                departement=ville["departement"],
                experience_codes=experience_codes,
                types_contrat=types_contrat,
            )
            for o in offres:
                o["_recherche"] = label
                o["_ville_recherchee"] = ville["nom"]
                all_offers[o["id"]] = o
            time.sleep(0.3)  # courtoisie envers l'API

        # Recherche sans filtre géo pour capter le full remote (si activé)
        if inclure_remote:
            log.info("Recherche '%s' (national, pour le remote)...", label)
            offres = search_offers(
                token, mots_cles,
                departement=None,
                experience_codes=experience_codes,
                types_contrat=types_contrat,
            )
            for o in offres:
                if offer_mentions_remote(o, remote_keywords):
                    o["_recherche"] = label
                    o["_ville_recherchee"] = "Remote"
                    all_offers[o["id"]] = o
            time.sleep(0.3)

    # Filtrage: exclusions + nouveauté
    excluded_keywords = config.get("mots_cles_exclus", [])
    bonus_keywords = config.get("mots_cles_bonus", [])

    new_offers = []
    for offer_id, offer in all_offers.items():
        if offer_id in seen_ids:
            continue
        if offer_is_excluded(offer, excluded_keywords):
            continue
        offer["_score"] = score_offer(offer, bonus_keywords)
        offer["_is_remote"] = offer_mentions_remote(offer, remote_keywords)
        new_offers.append(offer)

    # Tri par score décroissant puis date de création décroissante
    new_offers.sort(key=lambda o: (o["_score"], o.get("dateCreation", "")), reverse=True)

    return new_offers


def update_history(new_offers: list[dict]) -> list[dict]:
    """Conserve un historique des derniers jours pour affichage (pas seulement le jour J)."""
    history = []
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)

    today_entry = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "count": len(new_offers),
        "offres": new_offers,
    }
    history.insert(0, today_entry)
    history = history[:14]  # garde les 14 derniers jours

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return history


# ---------------------------------------------------------------------------
# Entrée principale
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Démarrage du job alert ===")
    config = load_config()
    seen_ids = load_seen_offers()
    log.info("%d offres déjà vues en base.", len(seen_ids))

    token = get_access_token()
    log.info("Authentification OK.")

    new_offers = collect_new_offers(config, token, seen_ids)
    log.info("%d nouvelles offres trouvées.", len(new_offers))

    # Mise à jour de l'état "vu"
    seen_ids.update(o["id"] for o in new_offers)
    save_seen_offers(seen_ids)

    history = update_history(new_offers)

    # Génération du HTML (import local pour éviter dépendance circulaire)
    from generate_html import generate_dashboard
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    generate_dashboard(history, HTML_OUTPUT_PATH)
    log.info("Dashboard généré: %s", HTML_OUTPUT_PATH)

    log.info("=== Fin ===")


if __name__ == "__main__":
    main()