"""
Projet DourData — rendement du réseau et pertes en eau potable,
pour un département français ou pour la France entière, via l'API Hub'Eau.

Indicateurs récupérés (SISPEA) :
  - P104.3 : rendement du réseau de distribution (%)
  - P106.3 : indice linéaire de pertes en réseau (m3/km/j)

Point clé : l'endpoint /indicateurs de l'API Hub'Eau n'accepte AUCUN filtre
géographique (ni code_departement, ni code_commune) — seulement annee,
code_indicateur, page, size. Le bon endpoint pour filtrer par département
est /communes, qui renvoie en prime les deux indicateurs directement dans
un objet imbriqué "indicateurs" pour chaque commune et chaque année : un
seul appel suffit donc pour P104.3 et P106.3.

Usage :
    source .venv/bin/activate
    python rendements.py --departement 35   # un seul département -> rendements_35.csv
    python rendements.py --all               # France entière -> rendements_national.csv

Le mode --all interroge l'API département par département (elle ne permet
pas de filtrer sur plusieurs départements en un seul appel) et met en cache
le résultat brut de chaque département dans .cache/, pour pouvoir reprendre
un run interrompu sans re-télécharger ce qui a déjà été récupéré.
"""

import argparse
import json
import time
from pathlib import Path

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://hubeau.eaufrance.fr/api/v0/indicateurs_services/communes"
TYPE_SERVICE = "AEP"     # Alimentation en Eau Potable (on exclut assainissement AC/ANC)
CACHE_DIR = Path(".cache")

RENDEMENT_COL = "indicateurs.P104.3"
PERTES_COL = "indicateurs.P106.3"

# Départements français : métropole (avec la Corse en 2A/2B) + DOM.
# Saint-Pierre-et-Miquelon (975) est une collectivité, pas un département,
# et n'est pas couvert par SISPEA : on ne l'inclut pas.
DEPARTEMENTS = (
    [f"{i:02d}" for i in range(1, 20)]
    + ["2A", "2B"]
    + [f"{i:02d}" for i in range(21, 96)]
    + ["971", "972", "973", "974", "976"]
)


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
    """Récupère toutes les pages de résultats de l'API Hub'Eau pour ces params."""
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
                print(f"    ! souci réseau (page {page}, essai {attempt+1}/3) : {e}")
                print(f"      nouvelle tentative dans {wait}s...")
                time.sleep(wait)
        else:
            raise SystemExit(f"Abandon : l'API n'a pas répondu pour la page {page}.")

        payload = r.json()
        data = payload.get("data", [])
        records.extend(data)
        if not payload.get("next"):
            break
        page += 1
    return records


def fetch_departement(session: requests.Session, dept: str, use_cache: bool = True) -> list[dict]:
    """Récupère (ou relit depuis le cache) les enregistrements d'un département."""
    cache_file = CACHE_DIR / f"communes_{dept}.json"
    if use_cache and cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    records = fetch_all(session, {"code_departement": dept, "type_service": TYPE_SERVICE})

    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(records, f)

    return records


def build_dataframe(records: list[dict]) -> pd.DataFrame:
    """Transforme les enregistrements bruts en un tableau, une ligne par
    commune (année la plus récente disponible), trié du pire au meilleur
    rendement."""
    df = pd.json_normalize(records)

    for col in (RENDEMENT_COL, PERTES_COL):
        if col not in df.columns:
            raise SystemExit(f"Champ {col} introuvable — colonnes disponibles : {list(df.columns)}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Pour chaque commune, on garde l'année la plus récente où le rendement est renseigné
    df_valid = df.dropna(subset=[RENDEMENT_COL])
    df_latest = (
        df_valid.sort_values("annee")
        .groupby("code_commune_insee", as_index=False)
        .last()
    )
    df_latest = df_latest.sort_values(RENDEMENT_COL)  # du pire au meilleur

    df_latest["noms_service"] = df_latest["noms_service"].apply(
        lambda v: ", ".join(v) if isinstance(v, list) else v
    )
    df_latest["codes_service"] = df_latest["codes_service"].apply(
        lambda v: ", ".join(str(c) for c in v) if isinstance(v, list) else v
    )

    cols = ["code_commune_insee", "nom_commune", "annee",
            RENDEMENT_COL, PERTES_COL, "codes_service", "noms_service"]
    return df_latest[cols].rename(columns={
        RENDEMENT_COL: "rendement_reseau_pct",
        PERTES_COL: "indice_lineaire_pertes_m3_km_j",
    })


def print_summary(out: pd.DataFrame, label: str):
    print(f"=== Les 10 pires rendements ({label}) ===")
    print(out.head(10).to_string(index=False))
    print(f"\nRendement médian ({label}) : {out['rendement_reseau_pct'].median():.1f} %")


def run_departement(dept: str):
    session = make_session()
    print(f"Récupération des indicateurs eau potable pour le département {dept}...")
    records = fetch_departement(session, dept, use_cache=False)
    print(f"{len(records)} enregistrements récupérés (commune x année).\n")
    if not records:
        raise SystemExit("Aucune donnée renvoyée par l'API pour ce département.")

    out = build_dataframe(records)
    out_path = f"rendements_{dept}.csv"
    out.to_csv(out_path, index=False)

    print_summary(out, f"département {dept}")
    print(f"\nRésultat complet exporté dans {out_path}")


def run_national():
    session = make_session()
    all_records = []
    total = len(DEPARTEMENTS)

    for i, dept in enumerate(DEPARTEMENTS, start=1):
        cache_file = CACHE_DIR / f"communes_{dept}.json"
        cached = cache_file.exists()
        records = fetch_departement(session, dept, use_cache=True)
        all_records.extend(records)
        source = "cache" if cached else "API"
        print(f"[{i}/{total}] département {dept} : {len(records)} enregistrements ({source})")
        if not cached:
            time.sleep(0.5)  # petite pause de politesse entre deux départements

    print(f"\n{len(all_records)} enregistrements récupérés au total (commune x année).\n")

    out = build_dataframe(all_records)
    out_path = "rendements_national.csv"
    out.to_csv(out_path, index=False)

    print(f"Communes distinctes couvertes : {out['code_commune_insee'].nunique()}")
    print_summary(out, "France entière")
    print(f"\nRésultat complet exporté dans {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--departement", help="code INSEE du département (ex: 35, 2A, 971)")
    group.add_argument("--all", action="store_true", help="récupère tous les départements de France")
    args = parser.parse_args()

    if args.all:
        run_national()
    else:
        run_departement(args.departement)


if __name__ == "__main__":
    main()
