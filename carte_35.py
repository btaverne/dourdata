"""
Projet fuites-eau — carte interactive du rendement des réseaux d'eau potable
en Ille-et-Vilaine (dept 35).

Combine :
  - rendements_35.csv (généré par rendements_35.py) : rendement et pertes
    par commune, données SISPEA/Hub'Eau.
  - les contours géographiques des communes du 35, publiés par le projet
    open source "france-geojson" (dérivé des données IGN/Etalab).

Sortie :
    carte_rendements_35.html — carte autonome, ouvrable dans un navigateur
    sans connexion internet requise (les contours sont incorporés dans le
    fichier).

Usage :
    source .venv/bin/activate
    python carte_35.py
"""

import json

import branca.colormap as cm
import folium
import pandas as pd
import requests

CSV_PATH = "rendements_35.csv"
GEOJSON_URL = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/"
    "departements/35-ille-et-vilaine/communes-35-ille-et-vilaine.geojson"
)
OUTPUT_HTML = "carte_rendements_35.html"


def main():
    df = pd.read_csv(CSV_PATH, dtype={"code_commune_insee": str})
    data_by_code = df.set_index("code_commune_insee").to_dict(orient="index")

    print("Téléchargement des contours des communes du 35...")
    geo = requests.get(GEOJSON_URL, timeout=60).json()

    # On enrichit chaque forme géographique avec les données de rendement,
    # pour pouvoir les afficher directement dans les info-bulles de la carte.
    missing = []
    for feature in geo["features"]:
        code = feature["properties"]["code"]
        row = data_by_code.get(code)
        if row is None:
            missing.append(code)
            feature["properties"]["rendement_reseau_pct"] = None
            feature["properties"]["indice_lineaire_pertes_m3_km_j"] = None
            feature["properties"]["annee"] = None
        else:
            feature["properties"]["rendement_reseau_pct"] = row["rendement_reseau_pct"]
            feature["properties"]["indice_lineaire_pertes_m3_km_j"] = row[
                "indice_lineaire_pertes_m3_km_j"
            ]
            feature["properties"]["annee"] = row["annee"]

    if missing:
        print(f"! {len(missing)} commune(s) du CSV sans contour géographique "
              f"(probablement fusionnées depuis) : {missing}")

    # Échelle de couleur : rouge (mauvais rendement) -> vert (bon rendement)
    colormap = cm.LinearColormap(
        colors=["#d73027", "#fee08b", "#1a9850"],
        vmin=df["rendement_reseau_pct"].min(),
        vmax=df["rendement_reseau_pct"].max(),
        caption="Rendement du réseau d'eau potable (%)",
    )

    def style_function(feature):
        valeur = feature["properties"]["rendement_reseau_pct"]
        return {
            "fillColor": colormap(valeur) if valeur is not None else "#cccccc",
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.75,
        }

    carte = folium.Map(location=[48.15, -1.85], zoom_start=9, tiles="cartodbpositron")

    folium.GeoJson(
        geo,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["nom", "rendement_reseau_pct", "indice_lineaire_pertes_m3_km_j", "annee"],
            aliases=["Commune :", "Rendement réseau (%) :", "Pertes (m³/km/j) :", "Année :"],
            localize=True,
        ),
    ).add_to(carte)

    colormap.add_to(carte)
    carte.save(OUTPUT_HTML)
    print(f"Carte enregistrée dans {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
