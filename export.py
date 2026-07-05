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

Le répertoire de sortie est paramétrable (--outdir). En mode --all, une page
index.html de téléchargement est aussi générée, ce qui permet de publier le
tout comme site statique (par ex. dans docs/ pour GitHub Pages) :
    python export.py --all --outdir docs

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

# Noms des départements (pour la page de téléchargement).
DEPT_NOMS = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
    "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse",
    "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir",
    "29": "Finistère", "30": "Gard", "31": "Haute-Garonne", "32": "Gers",
    "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre",
    "37": "Indre-et-Loire", "38": "Isère", "39": "Jura", "40": "Landes",
    "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique",
    "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère",
    "49": "Maine-et-Loire", "50": "Manche", "51": "Marne", "52": "Haute-Marne",
    "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan",
    "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise", "61": "Orne",
    "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin",
    "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire",
    "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris",
    "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise", "971": "Guadeloupe", "972": "Martinique",
    "973": "Guyane", "974": "La Réunion", "976": "Mayotte",
}

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
    ("donnee_suspecte",                 "Donnée suspecte (voir LISEZMOI)",               None),
]


def dep_of(insee: str) -> str:
    """Code département depuis le code INSEE (3 car. pour l'outre-mer, 2 sinon)."""
    return insee[:3] if insee[:2] in ("97", "98") else insee[:2]


def flag_suspecte(df: pd.DataFrame) -> pd.Series:
    """Marque les lignes dont la donnée est probablement aberrante, à ne pas
    citer telle quelle. Règles (transparentes) — « oui » si AU MOINS une :
      - rendement <= 0 % ou > 100 % (physiquement impossible : erreur de saisie) ;
      - avis qualité SISPEA « Anomalie » ou « Présomption d'anomalie » ;
      - volume de pertes du service manquant (données de base incomplètes).

    NB : l'avis « Non vérifié » (donnée récente pas encore validée par les
    services de l'État) n'est PAS traité comme suspect — il concerne ~98 % du
    dernier millésime et reste signalé dans la colonne « Avis qualité SISPEA ».
    """
    rend = df["rendement_reseau_pct"]
    avis = df["avis_qualite_sispea"].fillna("").str.strip()
    vol = df["volume_pertes_service_m3_an"]
    suspecte = (
        rend.isna() | (rend <= 0) | (rend > 100)
        | (avis == "Anomalie")
        | avis.str.contains("résomption|resomption", case=False, regex=True)
        | vol.isna()
    )
    return suspecte.map({True: "oui", False: "non"})


def load_source() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_CSV, dtype={"code_commune_insee": str, "codes_service": str})
    df["departement"] = df["code_commune_insee"].map(dep_of)
    df["donnee_suspecte"] = flag_suspecte(df)
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
    n_susp = int((df["donnee_suspecte"] == "oui").sum())
    lignes += [
        "",
        "Colonne « Donnée suspecte » — à lire avant de citer un chiffre",
        "-" * 74,
        "Une ligne est marquée « oui » si AU MOINS un de ces cas est vrai :",
        "  - rendement <= 0 % ou > 100 % (physiquement impossible : erreur de saisie) ;",
        "  - avis qualité SISPEA « Anomalie » ou « Présomption d'anomalie » ;",
        "  - volume de pertes du service manquant (données de base incomplètes).",
        f"Concerne {n_susp} communes sur {len(df)}. Ces lignes NE sont PAS supprimées",
        "(transparence) : elles restent dans le fichier mais ne doivent pas être",
        "citées comme des mesures fiables. À l'inverse, l'avis « Non vérifié » n'est",
        "PAS considéré comme suspect : c'est l'état normal d'une donnée récente pas",
        "encore validée par les services de l'État, pas une anomalie.",
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


def write_index_html(outdir: Path, df: pd.DataFrame):
    """Page d'accueil statique listant les fichiers téléchargeables."""
    mil = millesime_str(df)
    counts = df["conformite_decret_fuites"].value_counts()
    n_total = f"{len(df):,}".replace(",", " ")       # espace insécable
    n_nc = f"{int(counts.get('non conforme', 0)):,}".replace(",", " ")

    # Une carte de téléchargement par département présent.
    deps = sorted(df["departement"].unique(), key=lambda d: (len(d), d))
    cartes = []
    for dep in deps:
        nb = int((df["departement"] == dep).sum())
        nom = DEPT_NOMS.get(dep, dep)
        cartes.append(
            f'<a class="dep" href="departements/dourdata_{dep}.csv" download>'
            f'<b>{dep}</b> {nom} <span>({nb})</span></a>'
        )
    grille = "\n".join(cartes)

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DourData — l'eau perdue par les réseaux d'eau potable</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto;
         padding: 24px; color: #222; line-height: 1.5; }}
  h1 {{ margin-bottom: 4px; }}
  .sub {{ color: #666; margin-top: 0; }}
  .stat {{ background: #f0f7f4; border: 1px solid #cbe3d8; border-radius: 8px;
           padding: 12px 16px; margin: 18px 0; }}
  .dl {{ display: inline-block; background: #1a7f52; color: #fff; padding: 10px 18px;
         border-radius: 6px; text-decoration: none; font-weight: 600; }}
  .grille {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
             gap: 6px; margin-top: 12px; }}
  .dep {{ display: block; padding: 7px 10px; border: 1px solid #ddd; border-radius: 5px;
          text-decoration: none; color: #222; font-size: 14px; }}
  .dep:hover {{ background: #f0f7f4; border-color: #1a7f52; }}
  .dep span {{ color: #888; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee;
            color: #666; font-size: 13px; }}
  a {{ color: #1a7f52; }}
</style>
</head>
<body>
  <h1>DourData 💧</h1>
  <p class="sub">L'eau perdue par les fuites des réseaux d'eau potable, commune par commune.
     Données SISPEA, millésime {mil}.</p>

  <div class="stat">
    <b>{n_total}</b> communes couvertes — dont <b>{n_nc}</b> non conformes au décret
    « fuites ». Chaque fichier CSV contient le rendement du réseau, le volume d'eau perdu
    estimé, les équivalents parlants et le statut de conformité.
  </div>

  <h2>Télécharger les données</h2>
  <p><a class="dl" href="dourdata_national.csv" download>⬇ France entière (CSV)</a>
     &nbsp; <a href="LISEZMOI.txt">Notice &amp; méthodologie</a></p>

  <h3>Par département</h3>
  <p>Utile pour un collectif local. Le nombre de communes est indiqué entre parenthèses.</p>
  <div class="grille">
    {grille}
  </div>

  <footer>
    Source : SISPEA, via data.gouv.fr / services.eaufrance.fr —
    {LICENCE}.<br>
    Fichiers : séparateur « ; », décimale « , », UTF-8 (ouverture directe dans Excel FR).
    Conformité au décret fuites <b>indicative</b> (voir la notice).<br>
    Code &amp; méthodologie : <a href="{METHODO_URL}">{METHODO_URL}</a>
  </footer>
</body>
</html>
"""
    (outdir / "index.html").write_text(html, encoding="utf-8")


def run_all(df: pd.DataFrame, outdir: Path, site: bool = False):
    mil = millesime_str(df)
    # Tri neutre par code INSEE : la première ligne n'est jamais une donnée
    # aberrante (l'ancien tri par rendement mettait les 0 % artificiels en tête).
    national = df.sort_values("code_commune_insee")
    write_csv(build_export(national), outdir / "dourdata_national.csv", mil, "France entière")
    dep_dir = outdir / "departements"
    for dep, sub in df.groupby("departement"):
        write_csv(build_export(sub.sort_values("code_commune_insee")),
                  dep_dir / f"dourdata_{dep}.csv", millesime_str(sub),
                  f"Département {dep}")
    write_lisezmoi(outdir / "LISEZMOI.txt", df)
    if site:
        write_index_html(outdir, df)
    extra = " + page index.html" if site else ""
    print(f"Export national + {df['departement'].nunique()} départements{extra} -> {outdir}/")


def run_departement(df: pd.DataFrame, dep: str, outdir: Path):
    sub = df[df["departement"] == dep].sort_values("code_commune_insee")
    if sub.empty:
        raise SystemExit(f"Aucune donnée pour le département {dep}.")
    path = outdir / "departements" / f"dourdata_{dep}.csv"
    write_csv(build_export(sub), path, millesime_str(sub), f"Département {dep}")
    write_lisezmoi(outdir / "LISEZMOI.txt", df)
    print(f"Export du département {dep} ({len(sub)} communes) -> {path}")


def run_commune(df: pd.DataFrame, insee: str, outdir: Path):
    ligne = df[df["code_commune_insee"] == insee]
    if ligne.empty:
        raise SystemExit(f"Commune {insee} introuvable.")
    services = set(ligne["codes_service"])
    sub = df[df["codes_service"].isin(services)].sort_values("code_commune_insee")
    nom = ligne.iloc[0]["nom_commune"]
    path = outdir / "communes" / f"dourdata_{insee}.csv"
    write_csv(build_export(sub), path, millesime_str(sub),
              f"Commune {nom} ({insee}) et communes du même service")
    print(f"Export de {nom} ({insee}) + {len(sub) - 1} communes du même service -> {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="national + tous les départements")
    group.add_argument("--departement", help="code département (ex: 35, 2A, 971)")
    group.add_argument("--commune", help="code INSEE de la commune (ex: 35238)")
    parser.add_argument("--outdir", default="exports",
                        help="répertoire de sortie (défaut: exports ; ex: docs pour GitHub Pages)")
    parser.add_argument("--site", action="store_true",
                        help="génère aussi une page index.html (avec --all)")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    df = load_source()
    if args.all:
        run_all(df, outdir, site=args.site)
    elif args.departement:
        run_departement(df, args.departement, outdir)
    else:
        run_commune(df, args.commune, outdir)


if __name__ == "__main__":
    main()
