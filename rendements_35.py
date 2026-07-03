"""
Projet fuites-eau — Étape 1 : rendement du réseau et pertes en eau
pour les communes d'Ille-et-Vilaine (dept 35), via l'API Hub'Eau.

Indicateurs récupérés (SISPEA) :
  - P104.3 : rendement du réseau de distribution (%)
  - P106.3 : indice linéaire de pertes en réseau (m3/km/j)

Point clé : l'endpoint /indicateurs de l'API Hub'Eau n'accepte AUCUN filtre
géographique (ni code_departement, ni code_commune) — seulement annee,
code_indicateur, page, size. C'est pour ça que le script v1 récupérait la
France entière et plantait au-delà de la limite de pagination (20 000
résultats). Le bon endpoint pour filtrer par département est /communes,
qui renvoie en prime les deux indicateurs directement dans un objet
imbriqué "indicateurs" pour chaque commune et chaque année : un seul appel
suffit donc pour P104.3 et P106.3.

Usage :
    source .venv/bin/activate
    python rendements_35.py
Sortie :
    rendements_35.csv (une ligne par commune, année la plus récente
    disponible, classée du pire au meilleur rendement)
"""

import time
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://hubeau.eaufrance.fr/api/v0/indicateurs_services/communes"
DEPARTEMENT = "35"       # Ille-et-Vilaine
TYPE_SERVICE = "AEP"     # Alimentation en Eau Potable (on exclut assainissement AC/ANC)


def make_session() -> requests.Session:
    """Session HTTP avec retry auto sur les erreurs réseau/serveur."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_all(session: requests.Session, params: dict) -> list[dict]:
    """Récupère toutes les pages de résultats de l'API Hub'Eau."""
    records, page = [], 1
    while True:
        for attempt in range(3):
            try:
                r = session.get(
                    BASE_URL,
                    params={**params, "page": page, "size": 1000},
                    timeout=(10, 120),
                )
                r.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                wait = 5 * (attempt + 1)
                print(f"  ! souci réseau (page {page}, essai {attempt+1}/3) : {e}")
                print(f"    nouvelle tentative dans {wait}s...")
                time.sleep(wait)
        else:
            raise SystemExit(f"Abandon : l'API n'a pas répondu pour la page {page}.")

        payload = r.json()
        data = payload.get("data", [])
        records.extend(data)
        print(f"  page {page} : {len(data)} enregistrements (total {len(records)})")
        if not payload.get("next"):
            break
        page += 1
    return records


def main():
    session = make_session()
    print(f"Récupération des indicateurs eau potable pour le département {DEPARTEMENT}...")

    records = fetch_all(session, {
        "code_departement": DEPARTEMENT,
        "type_service": TYPE_SERVICE,
    })
    print(f"{len(records)} enregistrements récupérés (commune x année).\n")

    if not records:
        raise SystemExit("Aucune donnée renvoyée par l'API.")

    df = pd.json_normalize(records)

    rendement_col = "indicateurs.P104.3"
    pertes_col = "indicateurs.P106.3"
    for col in (rendement_col, pertes_col):
        if col not in df.columns:
            raise SystemExit(f"Champ {col} introuvable — colonnes disponibles : {list(df.columns)}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Info de couverture avant filtrage, utile pour repérer les trous
    print("Années disponibles :", sorted(df["annee"].unique().tolist()))
    print("Communes distinctes :", df["code_commune_insee"].nunique())
    print()

    # Pour chaque commune, on garde l'année la plus récente où le rendement est renseigné
    df_valid = df.dropna(subset=[rendement_col])
    df_latest = (
        df_valid.sort_values("annee")
        .groupby("code_commune_insee", as_index=False)
        .last()
    )
    df_latest = df_latest.sort_values(rendement_col)  # du pire au meilleur

    df_latest["noms_service"] = df_latest["noms_service"].apply(
        lambda v: ", ".join(v) if isinstance(v, list) else v
    )
    df_latest["codes_service"] = df_latest["codes_service"].apply(
        lambda v: ", ".join(str(c) for c in v) if isinstance(v, list) else v
    )

    cols = ["code_commune_insee", "nom_commune", "annee",
            rendement_col, pertes_col, "codes_service", "noms_service"]
    out = df_latest[cols].rename(columns={
        rendement_col: "rendement_reseau_pct",
        pertes_col: "indice_lineaire_pertes_m3_km_j",
    })
    out.to_csv("rendements_35.csv", index=False)

    print("=== Les 10 pires rendements d'Ille-et-Vilaine (données les plus récentes par commune) ===")
    print(out.head(10).to_string(index=False))
    print(f"\nRendement médian dans le 35 : {out['rendement_reseau_pct'].median():.1f} %")
    print("\nRésultat complet exporté dans rendements_35.csv")


if __name__ == "__main__":
    main()
