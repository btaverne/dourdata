# fuites-eau

Projet militant open source qui rend visible, pour chaque commune française, l'eau perdue par les
fuites de son réseau d'eau potable.

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

Les données proviennent de l'API [Hub'Eau — Indicateurs des services](https://hubeau.eaufrance.fr/page/api-indicateurs-services),
qui expose les indicateurs SISPEA (Système d'Information des Services Publics d'Eau et
d'Assainissement).

Point d'attention technique : l'endpoint `/indicateurs` de cette API n'accepte aucun filtre
géographique. Pour filtrer par département ou par commune, il faut utiliser l'endpoint
`/communes`, qui renvoie directement les indicateurs (dont P104.3 et P106.3) imbriqués par
commune et par année.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests pandas folium
```

## Utilisation

### 1. Récupérer les données

```bash
source .venv/bin/activate
python rendements_35.py
```

Le script interroge l'API Hub'Eau pour le département choisi, puis génère un fichier CSV listant
chaque commune avec son rendement de réseau et son indice linéaire de pertes, classé du pire au
meilleur rendement.

### 2. Générer la carte

```bash
source .venv/bin/activate
python carte_35.py
```

Ce script combine le CSV ci-dessus avec les contours géographiques des communes du 35 (fournis par
le projet open source [france-geojson](https://github.com/gregoiredavid/france-geojson), dérivé de
données IGN/Etalab) pour produire une carte interactive autonome : `carte_rendements_35.html`,
ouvrable directement dans un navigateur. Chaque commune est colorée du rouge (mauvais rendement) au
vert (bon rendement), avec le détail au survol.

Les fichiers CSV et HTML générés ne sont pas versionnés (voir `.gitignore`) : ce sont des données
téléchargées ou dérivées, pas du code source.
