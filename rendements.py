"""
Projet DourData — rendement du réseau et pertes en eau potable, par commune,
à partir des exports SISPEA publiés sur data.gouv.fr / services.eaufrance.fr.

Indicateurs :
  - P104.3 : rendement du réseau de distribution (%)
  - P106.3 : indice linéaire de pertes en réseau (m3/km/j)

Pourquoi cette source (et plus l'API Hub'Eau) : l'API Hub'Eau v0 est gelée à
2018-2019 (maintenance côté fournisseur). Les exports SISPEA « rapports
nationaux », eux, sont publiés jusqu'à 2024. On bascule donc dessus.

Deux fichiers par millésime sont nécessaires, car l'information y est éclatée
(là où l'API Hub'Eau livrait directement une ligne par commune) :

  A. Indicateurs — SISPEA_<annee>_AEP.xls (archive .7z), onglet
     « Entités de gestion », 1 ligne par service d'eau. Colonnes utiles :
       - « Id SISPEA de l'entité de gestion » = identifiant du service (clé)
       - « P104.3 », « P106.3 » = les deux indicateurs
     (pas de colonne année : tout le fichier correspond au millésime.)

  B. Composition communale — CompositionCommunaleServices_AEP_<annee>.xlsx
     (archive .zip), 1 ligne par couple (commune, service). Colonnes utiles :
       - « Code INSEE de la commune adhérente » = la commune
       - « Identifiant SISPEA de l'entité de gestion ... » = le service
         (même identifiant que la clé du fichier A)
       - « Année », « Nom de la commune adhérente », nom du service

Jointure : commune (B) -> identifiant du service -> indicateurs (A). Le
fichier B « explose » chaque service vers toutes les communes qu'il dessert,
ce que l'API Hub'Eau faisait auparavant automatiquement.

On traite plusieurs millésimes et, pour chaque commune, on retient l'année la
plus récente où un rendement est disponible. L'année est transportée jusque
dans le CSV de sortie (et donc jusqu'à l'infobulle de la carte).

Le format de sortie est identique à l'ancien (colonnes attendues par carte.py) :
    code_commune_insee, nom_commune, annee,
    rendement_reseau_pct, indice_lineaire_pertes_m3_km_j,
    codes_service, noms_service

Usage :
    source .venv/bin/activate
    python rendements.py --all              # -> rendements_national.csv
    python rendements.py --departement 35   # -> rendements_35.csv (filtre en sortie)

Les fichiers bruts téléchargés et décompressés sont mis en cache dans data/,
pour ne pas les re-télécharger à chaque exécution.
"""

import argparse
import zipfile
from pathlib import Path

import openpyxl
import pandas as pd
import py7zr
import requests

DATA_DIR = Path("data")

# Fenêtre de millésimes traités (du plus ancien au plus récent).
ANNEES = [2020, 2021, 2022, 2023, 2024]

# Indicateurs : URL "latest" data.gouv.fr de chaque archive .7z (contient un .xls).
INDICATEURS_URLS = {
    2020: "https://www.data.gouv.fr/api/1/datasets/r/65988ecb-d206-4f89-992f-2685030c2119",
    2021: "https://www.data.gouv.fr/api/1/datasets/r/c35fdf41-0d8d-4ba4-9cc8-b620e2ae231d",
    2022: "https://www.data.gouv.fr/api/1/datasets/r/ef88e155-cab1-4327-9ce3-f23b8d2a0307",
    2023: "https://www.data.gouv.fr/api/1/datasets/r/180d7556-7243-44dd-90dc-5490363cd792",
    2024: "https://www.data.gouv.fr/api/1/datasets/r/651de936-3f7b-41b3-bd94-58c00556b1d3",
}

# Composition communale : URL directe (services.eaufrance.fr), archive .zip (contient un .xlsx).
COMPO_URL_TPL = (
    "http://www.services.eaufrance.fr/documents/serviceMembers/"
    "CompositionCommunaleServices_AEP_{annee}.zip"
)

# Population municipale INSEE (populations de référence 2023, en vigueur au 1er
# janvier 2026). Sert aux équivalents « par habitant » et à la ventilation du
# volume de pertes d'un service vers ses communes, au prorata de la population.
POP_INSEE_URL = "https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.xlsx"
POP_INSEE_FILE = DATA_DIR / "insee_populations_2023.xlsx"

# Volume d'une piscine olympique (50 m x 25 m x 2 m), pour l'équivalent parlant.
PISCINE_OLYMPIQUE_M3 = 2500


# --------------------------------------------------------------------------
# Téléchargement + décompression (avec cache local dans data/)
# --------------------------------------------------------------------------

def download(url: str, dest: Path):
    """Télécharge url vers dest si le fichier n'est pas déjà en cache."""
    if dest.exists():
        return
    DATA_DIR.mkdir(exist_ok=True)
    print(f"    téléchargement {dest.name} ...")
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)


def indicateurs_file(annee: int) -> Path:
    """Retourne le chemin du tableur d'indicateurs pour l'année (télécharge et
    décompresse le .7z si besoin). Selon le millésime, le fichier interne est
    au format .xls (récents) ou .xlsx (plus anciens)."""
    archive = DATA_DIR / f"SISPEA_{annee}_AEP.7z"
    download(INDICATEURS_URLS[annee], archive)

    with py7zr.SevenZipFile(archive, "r") as z:
        names = [n for n in z.getnames() if n.lower().endswith((".xls", ".xlsx"))]
        if not names:
            raise SystemExit(f"Aucun tableur (.xls/.xlsx) dans {archive}")
        target = DATA_DIR / Path(names[0]).name
        if not target.exists():
            z.extract(path=DATA_DIR, targets=[names[0]])
            extracted = DATA_DIR / names[0]
            if extracted != target:
                extracted.rename(target)
    return target


def compo_xlsx(annee: int) -> Path:
    """Retourne le chemin du .xlsx de composition communale pour l'année
    (télécharge et décompresse le .zip si besoin)."""
    archive = DATA_DIR / f"CompositionCommunale_AEP_{annee}.zip"
    download(COMPO_URL_TPL.format(annee=annee), archive)

    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".xlsx")]
        if not names:
            raise SystemExit(f"Aucun .xlsx dans {archive}")
        target = DATA_DIR / Path(names[0]).name
        if not target.exists():
            with z.open(names[0]) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return target


def load_population_insee() -> dict:
    """Télécharge (si besoin) et lit le fichier population INSEE.
    Retourne {code_insee: population_municipale}.

    Le fichier couvre la France métropolitaine et la Corse ; les DOM n'y sont
    pas (ils n'apparaissent de toute façon pas sur la carte simplifiée). Le
    code INSEE se reconstitue en concaténant « Code département » et « Code
    commune »."""
    download(POP_INSEE_URL, POP_INSEE_FILE)
    wb = openpyxl.load_workbook(POP_INSEE_FILE, read_only=True, data_only=True)
    ws = wb["Communes"]

    rows = ws.iter_rows(values_only=True)
    # L'en-tête est précédé de lignes de titre ; on avance jusqu'à la ligne
    # d'en-tête (celle qui contient « Code commune ») puis on lit les données.
    for row in rows:
        if row and "Code commune" in [str(c).strip() if c else "" for c in row]:
            header = [str(c).strip() if c else "" for c in row]
            break
    else:
        raise SystemExit("En-tête 'Code commune' introuvable dans le fichier INSEE")

    i_dep = header.index("Code département")
    i_com = header.index("Code commune")
    i_pop = header.index("Population municipale")

    pop = {}
    for row in rows:
        dep, com, pmun = row[i_dep], row[i_com], row[i_pop]
        if dep is None or com is None:
            continue
        try:
            pop[f"{dep}{com}"] = int(pmun)
        except (TypeError, ValueError):
            continue
    return pop


# --------------------------------------------------------------------------
# Lecture / parsing des deux fichiers
# --------------------------------------------------------------------------

def _find_col(header: list, *,label: str, candidates) -> int:
    """Trouve l'index d'une colonne par égalité exacte de son en-tête (après
    strip). `candidates` est une liste de libellés possibles (tolérance aux
    variations entre millésimes)."""
    norm = [str(h).strip() if h is not None else "" for h in header]
    for cand in candidates:
        if cand in norm:
            return norm.index(cand)
    raise SystemExit(
        f"Colonne '{label}' introuvable. En-têtes disponibles : {norm}"
    )


def _to_float(v):
    """Convertit une valeur de cellule en float, ou None si vide / non numérique
    (les cellules SISPEA non renseignées valent souvent '' ou '-')."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# Le rendement P104.3 s'appelle « P104.3 » (exports récents, libellés lisibles)
# ou « p104_3 » (exports plus anciens, en-têtes techniques snake_case).
_RENDEMENT_HEADERS = ("P104.3", "p104_3")


def _has_rendement(header) -> bool:
    cells = [str(h).strip() if h is not None else "" for h in header]
    return any(h in cells for h in _RENDEMENT_HEADERS)


def _iter_indicateurs_rows(path: Path):
    """Générateur (header, puis lignes) tolérant au format .xls (xlrd) ou
    .xlsx (openpyxl). On sélectionne l'onglet contenant le rendement."""
    if path.suffix.lower() == ".xls":
        import xlrd
        wb = xlrd.open_workbook(path)
        for name in wb.sheet_names():
            sh = wb.sheet_by_name(name)
            if sh.nrows and _has_rendement([c.value for c in sh.row(0)]):
                yield [c.value for c in sh.row(0)]
                for r in range(1, sh.nrows):
                    yield [sh.cell_value(r, c) for c in range(sh.ncols)]
                return
        raise SystemExit(f"Aucun onglet avec le rendement dans {path.name}")
    else:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            header = next(rows, None)
            if header and _has_rendement(header):
                yield list(header)
                for r in rows:
                    yield list(r)
                return
        raise SystemExit(f"Aucun onglet avec le rendement dans {path.name}")


def parse_indicateurs(path: Path) -> dict:
    """Lit le tableur d'indicateurs (.xls ou .xlsx) et retourne, par service :
        {id_service: {
            'rendement'  : P104.3 (%)                     ou None,
            'pertes'     : P106.3 (indice, m3/km/j)       ou None,
            'lineaire'   : longueur de réseau (km, VP.077) ou None,
            'vol_conso'  : volume consommé autorisé (m3/an) ou None,
            'vol_pertes' : volume de pertes annuel (m3/an) ou None,
        }}

    Le volume de pertes est calculé par la « voie B » (la plus couvrante et
    directement dérivée de l'indicateur officiel) :
        volume de pertes = P106.3 x linéaire x 365.
    Le volume consommé autorisé est reconstitué depuis les variables brutes
        VP.063 + VP.201 + VP.220 + VP.221
    (comptabilisé domestique + non domestique + volume de service + consommé
    sans comptage). Ces deux reconstitutions ont été validées en recalculant
    P104.3 et P106.3 : elles coïncident à 99 % avec les valeurs publiées.
    """
    it = _iter_indicateurs_rows(path)
    header = next(it)
    i_id = _find_col(header, label="Id service",
                     candidates=["Id SISPEA de l'entité de gestion", "id_sispea_serv"])
    i_rend = _find_col(header, label="P104.3", candidates=["P104.3", "p104_3"])
    i_pertes = _find_col(header, label="P106.3", candidates=["P106.3", "p106_3"])
    i_lin = _find_col(header, label="VP.077 (linéaire)", candidates=["VP.077", "vp_077"])
    # Composantes du volume consommé autorisé.
    i_c1 = _find_col(header, label="VP.063", candidates=["VP.063", "vp_063"])
    i_c2 = _find_col(header, label="VP.201", candidates=["VP.201", "vp_201"])
    i_c3 = _find_col(header, label="VP.220", candidates=["VP.220", "vp_220"])
    i_c4 = _find_col(header, label="VP.221", candidates=["VP.221", "vp_221"])

    result = {}
    for row in it:
        sid = str(row[i_id]).strip()
        if sid.endswith(".0"):
            sid = sid[:-2]
        if not sid:
            continue

        pertes = _to_float(row[i_pertes])
        lineaire = _to_float(row[i_lin])
        vol_pertes = (
            pertes * lineaire * 365
            if pertes is not None and lineaire and lineaire > 0
            else None
        )

        # Volume consommé autorisé : somme des composantes présentes. On exige
        # au moins le volume comptabilisé domestique (VP.063) pour éviter un
        # total trompeur ; les autres composantes absentes sont comptées à 0.
        c1 = _to_float(row[i_c1])
        if c1 is None:
            vol_conso = None
        else:
            vol_conso = c1 + sum(_to_float(row[i]) or 0.0 for i in (i_c2, i_c3, i_c4))

        result[sid] = {
            "rendement": _to_float(row[i_rend]),
            "pertes": pertes,
            "lineaire": lineaire,
            "vol_conso": vol_conso,
            "vol_pertes": vol_pertes,
        }
    return result


def norm_insee(v) -> str:
    """Normalise un code INSEE : 5 caractères, zéro initial pour la métropole,
    inchangé pour la Corse (2A/2B) et l'outre-mer (97x/98x)."""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s and s[0].isdigit() and "A" not in s and "B" not in s:
        return s.zfill(5)
    return s


def parse_compo(xlsx_path: Path) -> list:
    """Lit le .xlsx de composition communale -> liste de tuples
    (code_insee, nom_commune, id_service, nom_service)."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    sh = wb[wb.sheetnames[0]]
    rows = sh.iter_rows(values_only=True)
    header = list(next(rows))

    i_insee = _find_col(header, label="Code INSEE commune",
                        candidates=["Code INSEE de la commune adhérente"])
    i_nom = _find_col(header, label="Nom commune",
                      candidates=["Nom de la commune adhérente"])
    i_svc = _find_col(header, label="Id service",
                      candidates=[
                          "Identifiant SISPEA de l'entité de gestion à laquelle la commune adhère",
                      ])
    i_svcnom = _find_col(header, label="Nom service",
                         candidates=[
                             "Nom de l'entité de gestion à laquelle la commune adhère",
                         ])

    out = []
    for r in rows:
        insee, sid = r[i_insee], r[i_svc]
        if insee is None or sid is None:
            continue
        sid = str(sid)
        if sid.endswith(".0"):
            sid = sid[:-2]
        out.append((
            norm_insee(insee),
            (str(r[i_nom]).strip() if r[i_nom] is not None else ""),
            sid,
            (str(r[i_svcnom]).strip() if r[i_svcnom] is not None else ""),
        ))
    return out


# --------------------------------------------------------------------------
# Construction du jeu de données
# --------------------------------------------------------------------------

def build_year_rows(annee: int, pop_insee: dict) -> list:
    """Pour un millésime : jointure commune -> service -> indicateurs, puis
    calcul des équivalents parlants par commune.

    Les volumes (pertes, consommation) sont mesurés au niveau du SERVICE. Pour
    parler « par commune », on ventile le volume de pertes du service au
    prorata de la population municipale INSEE de chaque commune desservie :
        volume de pertes commune = volume de pertes service x (pop_commune / pop_service).
    Les ratios (jours de consommation, litres/habitant/jour) sont des
    propriétés du réseau : ils sont identiques pour toutes les communes d'un
    même service.
    """
    print(f"  millésime {annee} :")
    indic = parse_indicateurs(indicateurs_file(annee))
    compo = parse_compo(compo_xlsx(annee))
    print(f"    {len(indic)} services, {len(compo)} liens commune-service")

    # Première passe : population totale desservie par chaque service (somme
    # des populations INSEE de ses communes).
    pop_service = {}
    for insee, _nom, sid, _svc in compo:
        pop_service[sid] = pop_service.get(sid, 0) + pop_insee.get(insee, 0)

    rows = []
    for insee, nom_commune, sid, nom_service in compo:
        ind = indic.get(sid)
        if ind is None:
            continue

        pop_comm = pop_insee.get(insee)
        pop_svc = pop_service.get(sid, 0)
        vol_pertes_svc = ind["vol_pertes"]
        vol_conso_svc = ind["vol_conso"]

        # Volume de pertes ventilé sur la commune (au prorata de sa population).
        vol_pertes_commune = None
        piscines = None
        if vol_pertes_svc is not None and pop_comm and pop_svc > 0:
            vol_pertes_commune = vol_pertes_svc * (pop_comm / pop_svc)
            piscines = vol_pertes_commune / PISCINE_OLYMPIQUE_M3

        # Jours de consommation de la commune couverts par les pertes (ratio,
        # propre au service).
        jours_conso = None
        if vol_pertes_svc is not None and vol_conso_svc and vol_conso_svc > 0:
            jours_conso = vol_pertes_svc / vol_conso_svc * 365

        # Litres perdus par habitant et par jour (ratio, propre au service).
        litres_hab_jour = None
        if vol_pertes_svc is not None and pop_svc > 0:
            litres_hab_jour = vol_pertes_svc * 1000 / pop_svc / 365

        rows.append({
            "code_commune_insee": insee,
            "nom_commune": nom_commune,
            "annee": annee,
            "rendement_reseau_pct": ind["rendement"],
            "indice_lineaire_pertes_m3_km_j": ind["pertes"],
            "volume_pertes_commune_m3_an": vol_pertes_commune,
            "piscines_olympiques_an": piscines,
            "jours_conso_commune": jours_conso,
            "litres_perdus_hab_jour": litres_hab_jour,
            "population_insee": pop_comm,
            "codes_service": sid,
            "noms_service": nom_service,
        })
    return rows


def build_dataframe() -> pd.DataFrame:
    """Traite tous les millésimes, empile, puis retient pour chaque commune
    l'année la plus récente où un rendement est renseigné."""
    print("Chargement de la population INSEE...")
    pop_insee = load_population_insee()

    all_rows = []
    for annee in ANNEES:
        all_rows.extend(build_year_rows(annee, pop_insee))

    df = pd.DataFrame(all_rows)

    # On ne garde que les lignes où le rendement est réellement renseigné,
    # puis, pour chaque commune, la ligne de l'année la plus récente.
    df = df.dropna(subset=["rendement_reseau_pct"])
    df = (
        df.sort_values("annee")
        .groupby("code_commune_insee", as_index=False)
        .last()
    )
    return df.sort_values("rendement_reseau_pct")  # du pire au meilleur


def print_summary(out: pd.DataFrame, label: str):
    print(f"\n=== Les 10 pires rendements ({label}) ===")
    cols = ["code_commune_insee", "nom_commune", "annee",
            "rendement_reseau_pct", "indice_lineaire_pertes_m3_km_j"]
    print(out[cols].head(10).to_string(index=False))
    print(f"\nRendement médian ({label}) : {out['rendement_reseau_pct'].median():.1f} %")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--departement", help="code INSEE du département (ex: 35, 2A, 971)")
    group.add_argument("--all", action="store_true", help="France entière")
    args = parser.parse_args()

    print("Construction du jeu de données à partir des exports SISPEA...")
    df = build_dataframe()

    if args.all:
        out = df
        out_path, label = "rendements_national.csv", "France entière"
    else:
        dept = args.departement
        out = df[df["code_commune_insee"].str.startswith(dept)]
        out_path, label = f"rendements_{dept}.csv", f"département {dept}"

    out.to_csv(out_path, index=False)
    print(f"\nMillésime le plus récent couvert : {int(df['annee'].max())}")
    print(f"Communes avec une donnée : {len(out)}")
    print_summary(out, label)
    print(f"\nRésultat complet exporté dans {out_path}")


if __name__ == "__main__":
    main()
