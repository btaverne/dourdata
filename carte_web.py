"""
Projet DourData — génération de la carte web légère (publiable sur GitHub Pages).

Contrairement à carte.py (folium, ~30 Mo, pratique pour l'exploration locale mais
trop lourd à publier), ce script produit une carte optimisée pour le web :

  - géométrie des communes SIMPLIFIÉE (Mapshaper, Visvalingam) et encodée en
    TopoJSON (frontières partagées stockées une seule fois) ;
  - données (rendement, conformité, équivalents) dans un fichier JSON compact
    séparé, ce qui allège la géométrie et permet au navigateur de la mettre en
    cache indépendamment des données ;
  - une page index.html (template statique, versionné) qui charge les deux via
    Leaflet + topojson-client.

Poids obtenu : ~7 Mo bruts, mais ~2 Mo réellement transférés (GitHub Pages sert
en gzip) — contre 30 Mo pour la version folium. La géométrie a un plancher
incompressible (~5 Mo bruts / 1,3 Mo gzip) car on préserve les 34 000 communes
sans en supprimer aucune (option keep-shapes).

Prérequis : Node.js + Mapshaper (`npm install -g mapshaper`).

Usage :
    source .venv/bin/activate
    python carte_web.py          # régénère docs/communes.topojson + docs/data.json

La carte elle-même (docs/index.html) est un template statique versionné, non régénéré.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from carte import load_geojson  # réutilise le téléchargement/cache des contours

SOURCE_CSV = "rendements_national.csv"
OUT_DIR = Path("docs")  # la carte (index.html) est en page d'accueil ; ses données à la racine
GEOJSON_CACHE = Path(".cache/communes_france_simplifiee.geojson")

SIMPLIFY = "5%"        # % de points conservés (Visvalingam)
QUANTIZATION = 3000    # grille de quantization TopoJSON (compromis poids/précision)

# Codes courts de conformité (pour alléger data.json).
CONF_MAP = {"conforme": "C", "non conforme": "N", "non calculable": "X"}
# Ordre des champs dans data.json (documenté aussi dans le fichier lui-même).
CHAMPS = ["rendement_pct", "conformite(C/N/X)", "litres_hab_jour",
          "jours_conso", "volume_pertes_commune_m3", "piscines_an", "annee"]


def ensure_mapshaper():
    if shutil.which("mapshaper") is None:
        sys.exit("Mapshaper introuvable. Installe-le : npm install -g mapshaper")


def ensure_geojson():
    """Garantit la présence du GeoJSON des contours (via le cache de carte.py)."""
    if not GEOJSON_CACHE.exists():
        print("Téléchargement des contours des communes...")
        load_geojson()  # écrit le cache


def _num(x, dec=0):
    if pd.isna(x):
        return None
    return round(float(x), dec) if dec else int(round(x))


def write_join_csv(df: pd.DataFrame, path: Path):
    """CSV minimal (code + rendement + conformité) pour la jointure Mapshaper :
    sert à ne garder que les communes présentes dans le jeu de données."""
    pd.DataFrame({
        "code": df["code_commune_insee"],
        "rend": df["rendement_reseau_pct"].round(1),
        "conf": df["conformite_decret_fuites"].map(CONF_MAP),
    }).to_csv(path, index=False)


def build_topojson(join_csv: Path):
    """Appelle Mapshaper : jointure, filtre des communes du jeu de données,
    simplification préservant la topologie, export TopoJSON."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "mapshaper", str(GEOJSON_CACHE),
        "-join", str(join_csv), "keys=code,code", "string-fields=code,conf",
        "-filter", '"rend" in this.properties && this.properties.rend != null',
        "-filter-fields", "code,nom",
        "-simplify", "visvalingam", SIMPLIFY, "keep-shapes",
        "-o", "format=topojson", f"quantization={QUANTIZATION}",
        str(OUT_DIR / "communes.topojson"),
    ]
    subprocess.run(cmd, check=True)


def write_data_json(df: pd.DataFrame, path: Path):
    """Données par commune, au format tableau compact (pas de clés répétées)."""
    data = {}
    for _, r in df.iterrows():
        data[r["code_commune_insee"]] = [
            _num(r["rendement_reseau_pct"], 1),
            CONF_MAP.get(r["conformite_decret_fuites"], "X"),
            _num(r["litres_perdus_hab_jour"]),
            _num(r["jours_conso_commune"]),
            _num(r["volume_pertes_commune_m3_an"]),
            _num(r["piscines_olympiques_an"], 1),
            _num(r["annee"]),
        ]
    payload = {"meta": {"champs": CHAMPS}, "communes": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))


def main():
    ensure_mapshaper()
    ensure_geojson()
    df = pd.read_csv(SOURCE_CSV, dtype={"code_commune_insee": str})

    tmp_csv = Path(".tmp"); tmp_csv.mkdir(exist_ok=True)
    join_csv = tmp_csv / "data_carte_join.csv"
    write_join_csv(df, join_csv)

    print(f"Simplification Mapshaper ({SIMPLIFY}, quantization {QUANTIZATION})...")
    build_topojson(join_csv)

    write_data_json(df, OUT_DIR / "data.json")

    topo = OUT_DIR / "communes.topojson"
    data = OUT_DIR / "data.json"
    mo = lambda p: p.stat().st_size / 1_048_576
    print(f"\nGénéré dans {OUT_DIR}/ :")
    print(f"  communes.topojson : {mo(topo):.1f} Mo")
    print(f"  data.json         : {mo(data):.1f} Mo")
    print(f"  (docs/index.html : la carte, template statique déjà versionné)")


if __name__ == "__main__":
    main()
