"""
Projet DourData — génération des exports CSV réutilisables.

Produit des fichiers CSV « prêts à l'emploi » pour un public associatif /
militant : colonnes lisibles, arrondis raisonnables, encodage compatible
Excel français, et surtout traçabilité (source, licence, millésime, date de
génération) pour qu'un fichier transmis à un tiers prouve son origine.

Trois niveaux :
    python export.py --all             # national + un fichier par département
    python export.py --departement 35  # un seul département
    python export.py --commune 35238   # une commune + les autres communes de son service

Choix de format (documentés) :
  - Séparateur « ; » et décimale « , » : convention française, ouverture
    directe dans Excel FR par double-clic.
  - Encodage UTF-8 avec BOM (utf-8-sig) : Excel FR affiche correctement les
    accents.
  - En-tête de métadonnées en lignes « # » (la traçabilité voyage avec le
    fichier) + un LISEZMOI.txt global. Dans Excel, ces lignes « # »
    apparaissent dans la colonne A avant le tableau ; on peut les supprimer
    pour un tableau nu.

Entrée : rendements_national.csv (généré par rendements.py).
Sortie : dossier exports/.
"""

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

SOURCE_CSV = "rendements_national.csv"
EXPORT_DIR = Path("exports")

LICENCE = "Licence Ouverte 2.0 (Etalab)"
SOURCE = ("SISPEA — Système d'Information des Services Publics d'Eau et "
          "d'Assainissement, via data.gouv.fr / services.eaufrance.fr")
METHODO_URL = "https://github.com/btaverne/dourdata"

# Colonnes de l'export : (colonne interne, libellé exporté, arrondi).
# arrondi = None -> texte ; 0 -> entier ; n -> n décimales.
COLONNES = [
    ("code_commune_insee",              "Code INSEE",                                    None),
    ("nom_commune",                     "Commune",                                       None),
    ("departement",                     "Département",                                   None),
    ("noms_service",                    "Service d'eau",                                 None),
    ("codes_service",                   "Identifiant SISPEA service",                    None),
    ("annee",                           "Année des données",                             0),
    ("rendement_reseau_pct",            "Rendement réseau P104.3 (%)",                   1),
    ("indice_lineaire_pertes_m3_km_j",  "Indice linéaire de pertes P106.3 (m3/km/j)",    1),
    ("indice_lineaire_conso_m3_km_j",   "Indice linéaire de consommation (m3/km/j)",     1),
    ("rendement_seuil_decret_pct",      "Rendement seuil décret fuites (%)",             1),
    ("conformite_decret_fuites",        "Conformité décret fuites",                      None),
    ("volume_pertes_service_m3_an",     "Volume de pertes du service (m3/an)",           0),
    ("volume_pertes_commune_m3_an",     "Volume de pertes estimé commune (m3/an, ventilé prorata population)", 0),
    ("litres_perdus_hab_jour",          "Litres perdus par habitant et par jour",        0),
    ("jours_conso_commune",             "Jours de consommation équivalents",             0),
    ("population_insee",                "Population INSEE",                               0),
    ("avis_qualite_sispea",             "Avis qualité SISPEA (rendement)",               None),
]


def dep_of(insee: str) -> str:
    """Code département depuis le code INSEE (3 car. pour l'outre-mer, 2 sinon)."""
    return insee[:3] if insee[:2] in ("97", "98") else insee[:2]


def load_source() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_CSV, dtype={"code_commune_insee": str, "codes_service": str})
    df["departement"] = df["code_commune_insee"].map(dep_of)
    return df


def build_export(df: pd.DataFrame) -> pd.DataFrame:
    """Sélectionne, arrondit et renomme les colonnes pour l'export."""
    out = pd.DataFrame()
    for interne, libelle, arrondi in COLONNES:
        col = df[interne]
        if arrondi == 0:
            col = col.round(0).astype("Int64")   # entier nullable (pas de .0)
        elif arrondi:
            col = col.round(arrondi)
        out[libelle] = col
    # Normalise les variantes d'avis (« Non verifie » sans accent des vieux millésimes).
    out["Avis qualité SISPEA (rendement)"] = (
        out["Avis qualité SISPEA (rendement)"]
        .replace({"Non verifie": "Non vérifié"})
    )
    return out


def _entete(millesime: str, perimetre: str) -> list:
    """Lignes de métadonnées (préfixées #) placées en tête de chaque CSV."""
    return [
        "# DourData — eau perdue par les réseaux d'eau potable (indicateurs SISPEA)",
        f"# Périmètre : {perimetre}",
        f"# Source : {SOURCE}",
        f"# Licence : {LICENCE}",
        f"# Millésime des données : {millesime} (année la plus récente disponible par commune)",
        f"# Date de génération de l'export : {date.today().isoformat()}",
        f"# Méthodologie et code : {METHODO_URL}",
        "# Format : séparateur « ; », décimale « , », encodage UTF-8 (BOM).",
        "# Les lignes commençant par # sont des métadonnées ; le tableau commence ci-dessous.",
    ]


def write_csv(df_export: pd.DataFrame, path: Path, millesime: str, perimetre: str):
    """Écrit un CSV avec en-tête de traçabilité, séparateur « ; », décimale
    « , » et encodage UTF-8 BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for ligne in _entete(millesime, perimetre):
            f.write(ligne + "\n")
        df_export.to_csv(f, sep=";", decimal=",", index=False, lineterminator="\n")


def millesime_str(df: pd.DataFrame) -> str:
    an_min, an_max = int(df["annee"].min()), int(df["annee"].max())
    return f"{an_max}" if an_min == an_max else f"{an_min}–{an_max}"


def write_lisezmoi(path: Path, df: pd.DataFrame):
    """LISEZMOI.txt global décrivant la source, la licence et les colonnes."""
    lignes = [
        "DourData — exports CSV des données de performance des réseaux d'eau potable",
        "=" * 74,
        "",
        f"Source          : {SOURCE}",
        f"Licence         : {LICENCE}",
        f"Millésime       : {millesime_str(df)} (année la plus récente disponible par commune)",
        f"Généré le       : {date.today().isoformat()}",
        f"Méthodologie    : {METHODO_URL}",
        "",
        "Format des fichiers",
        "-" * 74,
        "Séparateur de colonnes : point-virgule (;)",
        "Séparateur décimal     : virgule (,)   — convention française",
        "Encodage               : UTF-8 avec BOM (ouverture directe dans Excel FR)",
        "Chaque fichier débute par des lignes de métadonnées préfixées par #.",
        "",
        "Fichiers",
        "-" * 74,
        "dourdata_national.csv          : toutes les communes couvertes",
        "departements/dourdata_<dep>.csv : une commune par ligne, filtré par département",
        "",
        "Colonnes",
        "-" * 74,
    ]
    for _, libelle, _ in COLONNES:
        lignes.append(f"- {libelle}")
    lignes += [
        "",
        "Avertissements de lecture",
        "-" * 74,
        "- Les indicateurs sont mesurés à l'échelle du SERVICE d'eau, pas de la",
        "  commune : les communes d'un même service partagent les mêmes ratios.",
        "- Le « volume de pertes estimé commune » est le volume du service réparti",
        "  au prorata de la population : c'est une estimation, pas une mesure.",
        "- La conformité au décret fuites est indicative (cas des zones de",
        "  répartition des eaux non traité ; verdict prudent).",
        "- L'avis qualité « Non vérifié » signale une donnée récente pas encore",
        "  validée par les services de l'État (fréquent sur le dernier millésime).",
    ]
    path.write_text("\n".join(lignes), encoding="utf-8")


def run_all(df: pd.DataFrame):
    mil = millesime_str(df)
    # National
    write_csv(build_export(df), EXPORT_DIR / "dourdata_national.csv",
              mil, "France entière")
    # Par département
    dep_dir = EXPORT_DIR / "departements"
    for dep, sub in df.groupby("departement"):
        write_csv(build_export(sub.sort_values("code_commune_insee")),
                  dep_dir / f"dourdata_{dep}.csv", millesime_str(sub),
                  f"Département {dep}")
    write_lisezmoi(EXPORT_DIR / "LISEZMOI.txt", df)
    print(f"Export national + {df['departement'].nunique()} départements -> {EXPORT_DIR}/")


def run_departement(df: pd.DataFrame, dep: str):
    sub = df[df["departement"] == dep].sort_values("code_commune_insee")
    if sub.empty:
        raise SystemExit(f"Aucune donnée pour le département {dep}.")
    path = EXPORT_DIR / "departements" / f"dourdata_{dep}.csv"
    write_csv(build_export(sub), path, millesime_str(sub), f"Département {dep}")
    write_lisezmoi(EXPORT_DIR / "LISEZMOI.txt", df)
    print(f"Export du département {dep} ({len(sub)} communes) -> {path}")


def run_commune(df: pd.DataFrame, insee: str):
    ligne = df[df["code_commune_insee"] == insee]
    if ligne.empty:
        raise SystemExit(f"Commune {insee} introuvable.")
    # La commune + les autres communes de son service (contexte).
    services = set(ligne["codes_service"])
    sub = df[df["codes_service"].isin(services)].sort_values("code_commune_insee")
    nom = ligne.iloc[0]["nom_commune"]
    path = EXPORT_DIR / "communes" / f"dourdata_{insee}.csv"
    write_csv(build_export(sub), path, millesime_str(sub),
              f"Commune {nom} ({insee}) et communes du même service")
    print(f"Export de {nom} ({insee}) + {len(sub) - 1} communes du même service -> {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="national + tous les départements")
    group.add_argument("--departement", help="code département (ex: 35, 2A, 971)")
    group.add_argument("--commune", help="code INSEE de la commune (ex: 35238)")
    args = parser.parse_args()

    df = load_source()
    if args.all:
        run_all(df)
    elif args.departement:
        run_departement(df, args.departement)
    else:
        run_commune(df, args.commune)


if __name__ == "__main__":
    main()
