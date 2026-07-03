# DourData

Projet militant open source qui rend visible, pour chaque commune française, l'eau perdue par les
fuites de son réseau d'eau potable.

> « Dour » signifie « eau » en breton — DourData, ce sont les données de l'eau, rendues lisibles.

## Objectif

Les données de performance des services d'eau (SISPEA) sont publiques mais peu lisibles pour le
grand public. Ce projet extrait et met en forme, commune par commune, deux indicateurs clés :

- **P104.3** — rendement du réseau de distribution (%) : la part de l'eau produite qui arrive
  effectivement chez les usagers, le reste étant perdu par les fuites.
- **P106.3** — indice linéaire de pertes en réseau (m³/km/j) : le volume perdu par kilomètre de
  réseau et par jour, utile pour évaluer la conformité au décret « fuites » qui impose des seuils
  de rendement minimum aux services d'eau.

L'objectif est de permettre à chaque citoyen de voir, pour sa commune, si son service d'eau est
performant ou s'il gaspille une part importante de la ressource.

## Source des données

Les données proviennent des **exports SISPEA « rapports nationaux »** publiés sur
[data.gouv.fr](https://www.data.gouv.fr/datasets/services-publics-deau-potable-jeux-de-donnees-exploites-pour-les-rapports-nationaux-sispea-1)
et [services.eaufrance.fr](https://www.services.eaufrance.fr) (SISPEA = Système d'Information des
Services Publics d'Eau et d'Assainissement).

> **Pourquoi pas l'API Hub'Eau ?** Le projet utilisait au départ l'API Hub'Eau, plus simple. Mais
> celle-ci est **gelée à 2018-2019** (maintenance côté fournisseur). Les exports SISPEA, eux, sont
> publiés jusqu'à **2024**. On a donc basculé sur ces exports pour la fraîcheur des données.

L'information est répartie en **deux fichiers par millésime**, qu'il faut recomposer (là où l'API
Hub'Eau livrait directement une ligne par commune) :

- **Indicateurs** (`SISPEA_<année>_AEP`) : une ligne par service d'eau, avec le rendement (P104.3)
  et l'indice de pertes (P106.3), identifiés par un « Id SISPEA de l'entité de gestion ».
- **Composition communale** (`CompositionCommunaleServices_AEP_<année>`) : une ligne par couple
  commune–service, qui rattache chaque commune à l'identifiant de son service.

La jointure `commune → identifiant de service → indicateurs` reconstitue une ligne par commune. Le
script traite plusieurs millésimes (2020→2024) et retient, pour chaque commune, l'année la plus
récente où un rendement est disponible.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests pandas folium openpyxl xlrd py7zr
```

## Utilisation

### 1. Récupérer les données

```bash
source .venv/bin/activate

# La France entière -> rendements_national.csv
python rendements.py --all

# Un seul département (filtre en sortie) -> rendements_35.csv
python rendements.py --departement 35
```

Le script télécharge les exports SISPEA (indicateurs + composition communale) pour chaque millésime,
les décompresse, fait la jointure commune → service, et génère un CSV listant chaque commune avec son
rendement de réseau et son indice linéaire de pertes, classé du pire au meilleur rendement. L'année
retenue est conservée dans le CSV (et affichée dans l'infobulle de la carte).

Les fichiers bruts téléchargés sont mis en cache dans `data/` (non versionné) : ils ne sont pas
re-téléchargés aux exécutions suivantes.

### 2. Générer la carte

```bash
source .venv/bin/activate

# Un seul département
python carte.py --departement 35      # -> carte_rendements_35.html

# La France entière
python carte.py --all                 # -> carte_rendements_national.html
```

Ce script combine le CSV correspondant avec les contours géographiques des communes (fournis par
le projet open source [france-geojson](https://github.com/gregoiredavid/france-geojson), dérivé de
données IGN/Etalab) pour produire une carte interactive autonome, ouvrable directement dans un
navigateur. Chaque commune est colorée du rouge (mauvais rendement) au vert (bon rendement), avec
le détail au survol.

La carte nationale utilise la version simplifiée des contours (~19 Mo) pour rester fluide : elle
couvre la métropole (Corse comprise) mais pas les DOM, dont les communes restent présentes dans le
CSV sans apparaître sur la carte. Le fichier de contours est mis en cache dans `.cache/` après le
premier téléchargement.

Les fichiers CSV et HTML générés ne sont pas versionnés (voir `.gitignore`) : ce sont des données
téléchargées ou dérivées, pas du code source.
