#!/usr/bin/env python3
"""
Génère le dashboard HTML statique à partir de l'historique des offres.
Design: inspiré d'un pipeline CRM (univers du profil commercial ciblé).
"""

import html
from datetime import datetime
from pathlib import Path

# Seuils de score -> étiquette qualité de lead
def score_label(score: int) -> tuple[str, str]:
    if score >= 5:
        return "hot", "Lead chaud"
    if score >= 2:
        return "warm", "À qualifier"
    return "cold", "Découverte"


def fmt_date(date_str: str) -> str:
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year} à {dt.hour:02d}h{dt.minute:02d}"
    except (ValueError, AttributeError):
        return date_str


def offer_card_html(offer: dict) -> str:
    score = offer.get("_score", 0)
    badge_class, badge_label = score_label(score)
    titre = html.escape(offer.get("intitule", "Poste sans titre"))
    entreprise = html.escape((offer.get("entreprise") or {}).get("nom") or "Entreprise non précisée")
    lieu = html.escape((offer.get("lieuTravail") or {}).get("libelle") or offer.get("_ville_recherchee", ""))
    contrat = html.escape(offer.get("typeContratLibelle", offer.get("typeContrat", "")))
    desc_raw = offer.get("description", "")
    desc = html.escape(desc_raw[:220].rsplit(" ", 1)[0] + "…") if len(desc_raw) > 220 else html.escape(desc_raw)
    url = html.escape(offer.get("origineOffre", {}).get("urlOrigine") or
                       f"https://candidat.francetravail.fr/offres/recherche/detail/{offer.get('id', '')}")
    recherche = html.escape(offer.get("_recherche", ""))
    is_remote = offer.get("_is_remote", False)
    date_creation = fmt_date(offer.get("dateCreation", ""))

    remote_chip = '<span class="chip chip--remote">Remote</span>' if is_remote else ""

    return f"""
    <article class="card" data-score="{badge_class}">
      <div class="card__rail card__rail--{badge_class}"></div>
      <div class="card__body">
        <div class="card__top">
          <span class="badge badge--{badge_class}">{badge_label}</span>
          <span class="card__source">{recherche}</span>
        </div>
        <h3 class="card__title">{titre}</h3>
        <p class="card__company">{entreprise}</p>
        <div class="card__meta">
          <span class="chip">{lieu}</span>
          <span class="chip">{contrat}</span>
          {remote_chip}
        </div>
        <p class="card__desc">{desc}</p>
        <div class="card__footer">
          <span class="card__date">Publiée le {date_creation}</span>
          <a class="card__cta" href="{url}" target="_blank" rel="noopener noreferrer">Voir l'offre →</a>
        </div>
      </div>
    </article>"""


JOURS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def format_date_fr(dt: datetime) -> str:
    """Formate une date en français sans dépendre de la locale système."""
    return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month - 1]} {dt.year}"


def day_section_html(day: dict, is_first: bool) -> str:
    date_str = day["date"]
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        label = format_date_fr(dt)
        if date_str == today_str:
            label += " (aujourd'hui)"
    except ValueError:
        label = date_str

    offers = day.get("offres", [])
    count = len(offers)

    if count == 0:
        cards_html = '<p class="empty-state">Aucune nouvelle offre détectée ce jour-là. Le radar tourne, rien à signaler.</p>'
    else:
        cards_html = '<div class="grid">' + "".join(offer_card_html(o) for o in offers) + "</div>"

    open_attr = "open" if is_first else ""
    badge = f'<span class="day-count">{count} offre{"s" if count != 1 else ""}</span>'

    return f"""
    <details class="day" {open_attr}>
      <summary class="day__summary">
        <span class="day__label">{label}</span>
        {badge}
        <span class="day__chevron">▾</span>
      </summary>
      <div class="day__content">
        {cards_html}
      </div>
    </details>"""


def generate_dashboard(history: list[dict], output_path: Path) -> None:
    now = datetime.now()
    last_update = now.strftime("%d/%m/%Y à %Hh%M")
    total_today = history[0]["count"] if history else 0
    total_week = sum(d["count"] for d in history[:7])

    days_html = "".join(
        day_section_html(day, is_first=(i == 0)) for i, day in enumerate(history)
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pipeline · Veille emploi Adrien Lucas</title>
<style>
  :root {{
    --ink: #16201c;
    --ink-soft: #4a564f;
    --paper: #f6f5ef;
    --paper-raised: #ffffff;
    --line: #d8d6c8;
    --signal: #ff5a3c;
    --signal-soft: #ffe4dc;
    --hot: #d6452c;
    --hot-bg: #fdeae5;
    --warm: #b88a1f;
    --warm-bg: #fbf1da;
    --cold: #5b6a63;
    --cold-bg: #eceae0;
    --mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}

  a {{ color: inherit; }}

  .wrap {{
    max-width: 980px;
    margin: 0 auto;
    padding: 0 24px 80px;
  }}

  /* ---------- HEADER ---------- */
  header.hero {{
    padding: 56px 0 36px;
    border-bottom: 2px solid var(--ink);
    margin-bottom: 8px;
  }}

  .hero__eyebrow {{
    font-family: var(--mono);
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--signal);
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
  }}

  .hero__eyebrow::before {{
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--signal);
    box-shadow: 0 0 0 4px var(--signal-soft);
  }}

  h1.hero__title {{
    font-size: clamp(34px, 5vw, 52px);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin-bottom: 12px;
  }}

  .hero__sub {{
    color: var(--ink-soft);
    font-size: 16px;
    max-width: 560px;
    margin-bottom: 28px;
  }}

  .hero__stats {{
    display: flex;
    gap: 36px;
    flex-wrap: wrap;
  }}

  .stat {{
    display: flex;
    flex-direction: column;
  }}

  .stat__value {{
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 700;
  }}

  .stat__label {{
    font-size: 12px;
    color: var(--ink-soft);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}

  .hero__updated {{
    font-family: var(--mono);
    font-size: 12px;
    color: var(--ink-soft);
    margin-top: 28px;
  }}

  /* ---------- LEGEND ---------- */
  .legend {{
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    padding: 20px 0 32px;
    font-size: 13px;
    color: var(--ink-soft);
  }}

  .legend__item {{ display: flex; align-items: center; gap: 6px; }}
  .legend__dot {{ width: 9px; height: 9px; border-radius: 50%; }}
  .legend__dot--hot {{ background: var(--hot); }}
  .legend__dot--warm {{ background: var(--warm); }}
  .legend__dot--cold {{ background: var(--cold); }}

  /* ---------- DAY ACCORDION ---------- */
  details.day {{
    border-top: 1px solid var(--line);
    padding: 22px 0;
  }}

  details.day:last-of-type {{ border-bottom: 1px solid var(--line); margin-bottom: 24px; }}

  .day__summary {{
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: baseline;
    gap: 14px;
    font-family: var(--mono);
  }}

  .day__summary::-webkit-details-marker {{ display: none; }}

  .day__label {{
    font-size: 15px;
    font-weight: 700;
    text-transform: capitalize;
  }}

  .day-count {{
    font-size: 12px;
    color: var(--ink-soft);
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: 100px;
    padding: 2px 10px;
  }}

  .day__chevron {{
    margin-left: auto;
    transition: transform 0.2s ease;
    color: var(--ink-soft);
  }}

  details[open] .day__chevron {{ transform: rotate(180deg); }}

  .day__content {{ padding-top: 22px; }}

  .empty-state {{
    color: var(--ink-soft);
    font-size: 14px;
    font-style: italic;
    padding: 12px 0;
  }}

  /* ---------- GRID & CARDS ---------- */
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }}

  .card {{
    position: relative;
    background: var(--paper-raised);
    border: 1px solid var(--line);
    border-radius: 4px;
    overflow: hidden;
    display: flex;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }}

  .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(22, 32, 28, 0.08);
  }}

  .card__rail {{ width: 4px; flex-shrink: 0; }}
  .card__rail--hot {{ background: var(--hot); }}
  .card__rail--warm {{ background: var(--warm); }}
  .card__rail--cold {{ background: var(--cold); }}

  .card__body {{
    padding: 18px 18px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
    min-width: 0;
  }}

  .card__top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .badge {{
    font-family: var(--mono);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 100px;
  }}

  .badge--hot {{ background: var(--hot-bg); color: var(--hot); }}
  .badge--warm {{ background: var(--warm-bg); color: var(--warm); }}
  .badge--cold {{ background: var(--cold-bg); color: var(--cold); }}

  .card__source {{
    font-size: 11px;
    color: var(--ink-soft);
    font-family: var(--mono);
  }}

  .card__title {{
    font-size: 17px;
    font-weight: 700;
    line-height: 1.3;
  }}

  .card__company {{
    font-size: 13.5px;
    color: var(--ink-soft);
    font-weight: 500;
  }}

  .card__meta {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }}

  .chip {{
    font-size: 11.5px;
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: 100px;
    padding: 2px 9px;
    color: var(--ink-soft);
  }}

  .chip--remote {{
    background: #e8f3ec;
    border-color: #bfe0cb;
    color: #2f7a4d;
    font-weight: 600;
  }}

  .card__desc {{
    font-size: 13px;
    color: var(--ink-soft);
    line-height: 1.5;
    flex: 1;
  }}

  .card__footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px dashed var(--line);
  }}

  .card__date {{
    font-size: 10.5px;
    color: var(--ink-soft);
    font-family: var(--mono);
  }}

  .card__cta {{
    font-size: 12.5px;
    font-weight: 700;
    text-decoration: none;
    color: var(--signal);
    white-space: nowrap;
  }}

  .card__cta:hover {{ text-decoration: underline; }}

  footer.page-footer {{
    text-align: center;
    color: var(--ink-soft);
    font-size: 12px;
    font-family: var(--mono);
    padding-top: 30px;
  }}

  @media (max-width: 600px) {{
    .hero__stats {{ gap: 24px; }}
    header.hero {{ padding: 40px 0 28px; }}
  }}

  @media (prefers-reduced-motion: reduce) {{
    .card, .day__chevron {{ transition: none; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div class="hero__eyebrow">Pipeline actif</div>
      <h1 class="hero__title">Veille emploi — Adrien Lucas</h1>
      <p class="hero__sub">
        SDR/BDR · Account Executive · Account Manager — SaaS &amp; B2B.
        Paris, Lyon, Nantes &amp; full remote. Mise à jour automatique chaque jour
        via l'API France Travail.
      </p>
      <div class="hero__stats">
        <div class="stat">
          <span class="stat__value">{total_today}</span>
          <span class="stat__label">Nouvelles offres aujourd'hui</span>
        </div>
        <div class="stat">
          <span class="stat__value">{total_week}</span>
          <span class="stat__label">Cette semaine</span>
        </div>
      </div>
      <p class="hero__updated">Dernière synchronisation : {last_update}</p>
    </header>

    <div class="legend">
      <span class="legend__item"><span class="legend__dot legend__dot--hot"></span> Lead chaud — fort match avec ton profil</span>
      <span class="legend__item"><span class="legend__dot legend__dot--warm"></span> À qualifier — match partiel</span>
      <span class="legend__item"><span class="legend__dot legend__dot--cold"></span> Découverte — correspond aux critères de base</span>
    </div>

    {days_html}

    <footer class="page-footer">
      Généré automatiquement · Source : API France Travail · Ce site ne stocke aucune donnée personnelle
    </footer>
  </div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")


if __name__ == "__main__":
    # Permet de tester le rendu localement avec des données factices
    import json
    sample_history = [
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": 2,
            "offres": [
                {
                    "id": "test1",
                    "intitule": "Business Developer SaaS B2B",
                    "entreprise": {"nom": "Acme SaaS"},
                    "lieuTravail": {"libelle": "75 - Paris"},
                    "typeContratLibelle": "CDI",
                    "description": "Nous recherchons un BDR pour notre équipe commerciale, prospection outbound, HubSpot, cold calling quotidien...",
                    "dateCreation": datetime.now().isoformat(),
                    "_recherche": "SDR / BDR",
                    "_score": 6,
                    "_is_remote": True,
                    "_ville_recherchee": "Remote",
                    "origineOffre": {"urlOrigine": "https://example.com"},
                },
            ],
        }
    ]
    generate_dashboard(sample_history, Path("docs/index.html"))
    print("OK - test généré dans docs/index.html")
