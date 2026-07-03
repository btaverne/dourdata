"""
Projet DourData — carte interactive du rendement des réseaux d'eau potable,
pour un département ou pour la France entière.

Combine :
  - le CSV généré par rendements.py (rendements_<dept>.csv ou
    rendements_national.csv) : rendement et pertes par commune, données
    SISPEA/Hub'Eau.
  - les contours géographiques des communes de France (métropole + DOM),
    publiés par le projet open source "france-geojson" (dérivé des données
    IGN/Etalab).

On utilise la version simplifiée des contours (~19 Mo) pour garder une carte
fluide dans le navigateur. Elle couvre la France métropolitaine (Corse
comprise) mais PAS les DOM : les communes d'outre-mer restent présentes dans
le CSV mais n'apparaissent pas sur la carte. Le fichier de contours est mis
en cache dans .cache/ après le premier téléchargement.

Usage :
    source .venv/bin/activate
    python carte.py --departement 35   # -> carte_rendements_35.html
    python carte.py --all              # -> carte_rendements_national.html
"""

import argparse
import json
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd
import requests

GEOJSON_URL = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/"
    "communes-version-simplifiee.geojson"
)
CACHE_DIR = Path(".cache")
GEOJSON_CACHE = CACHE_DIR / "communes_france_simplifiee.geojson"


def load_geojson() -> dict:
    """Télécharge (ou relit depuis le cache) les contours de toutes les
    communes de France."""
    if GEOJSON_CACHE.exists():
        with open(GEOJSON_CACHE) as f:
            return json.load(f)

    print("Téléchargement des contours simplifiés des communes de France "
          "(~19 Mo, une seule fois)...")
    geo = requests.get(GEOJSON_URL, timeout=180).json()

    CACHE_DIR.mkdir(exist_ok=True)
    with open(GEOJSON_CACHE, "w") as f:
        json.dump(geo, f)
    return geo


def build_map(df: pd.DataFrame, geo: dict, caption_suffix: str) -> folium.Map:
    """Construit la carte : ne garde que les communes présentes dans le
    CSV, colorées selon leur rendement de réseau."""
    data_by_code = df.set_index("code_commune_insee").to_dict(orient="index")

    features = []
    for feature in geo["features"]:
        code = feature["properties"]["code"]
        row = data_by_code.get(code)
        if row is None:
            continue
        feature["properties"] = {
            "code": code,
            "nom": feature["properties"].get("nom"),
            "rendement_reseau_pct": row["rendement_reseau_pct"],
            "indice_lineaire_pertes_m3_km_j": row["indice_lineaire_pertes_m3_km_j"],
            "annee": row["annee"],
        }
        features.append(feature)

    present_codes = {f["properties"]["code"] for f in features}
    missing = set(df["code_commune_insee"]) - present_codes
    if missing:
        print(f"! {len(missing)} commune(s) du CSV sans contour géographique "
              f"correspondant (probablement fusionnées depuis).")

    filtered_geo = {"type": "FeatureCollection", "features": features}

    # Échelle de couleur : rouge (mauvais rendement) -> vert (bon rendement)
    colormap = cm.LinearColormap(
        colors=["#d73027", "#fee08b", "#1a9850"],
        vmin=df["rendement_reseau_pct"].min(),
        vmax=df["rendement_reseau_pct"].max(),
        caption=f"Rendement du réseau d'eau potable (%) — {caption_suffix}",
    )

    def style_function(feature):
        valeur = feature["properties"]["rendement_reseau_pct"]
        return {
            "fillColor": colormap(valeur) if valeur is not None else "#cccccc",
            "color": "black",
            "weight": 0.2,
            "fillOpacity": 0.75,
        }

    # prefer_canvas améliore beaucoup les performances quand il y a des
    # dizaines de milliers de formes (rendu Leaflet en Canvas plutôt qu'en SVG).
    carte = folium.Map(tiles="cartodbpositron", prefer_canvas=True)

    geojson_layer = folium.GeoJson(
        filtered_geo,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "rendement_reseau_pct", "indice_lineaire_pertes_m3_km_j", "annee"],
            aliases=["Commune :", "Rendement réseau (%) :", "Pertes (m³/km/j) :", "Année :"],
            localize=True,
        ),
    ).add_to(carte)

    colormap.add_to(carte)
    carte.fit_bounds(geojson_layer.get_bounds())
    return carte


def run(csv_path: str, out_path: str, caption_suffix: str):
    df = pd.read_csv(csv_path, dtype={"code_commune_insee": str})
    geo = load_geojson()
    carte = build_map(df, geo, caption_suffix)
    carte.save(out_path)
    print(f"Carte enregistrée dans {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--departement", help="code INSEE du département (ex: 35, 2A, 971)")
    group.add_argument("--all", action="store_true", help="carte de la France entière")
    args = parser.parse_args()

    if args.all:
        run("rendements_national.csv", "carte_rendements_national.html", "France entière")
    else:
        dept = args.departement
        run(f"rendements_{dept}.csv", f"carte_rendements_{dept}.html", f"département {dept}")


if __name__ == "__main__":
    main()
