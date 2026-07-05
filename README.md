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

## Équivalents parlants

Pour rendre les pertes concrètes, le script calcule par commune un **volume de pertes annuel** et
trois équivalents, affichés dans l'infobulle de la carte.

Le volume de pertes est calculé au niveau du **service** :
`volume de pertes = P106.3 (indice de pertes) × linéaire de réseau (VP.077) × 365`. Cette formule
a été validée en recalculant les indicateurs officiels P104.3 et P106.3 à partir des variables
brutes : le résultat coïncide à 99 % avec les valeurs publiées. À l'échelle nationale, le total
obtenu (~1 milliard de m³/an) correspond aux estimations officielles.

| Équivalent | Calcul | Remarque |
|---|---|---|
| Piscines olympiques/an | `volume de pertes commune / 2 500 m³` | Volume **ventilé** vers la commune au prorata de sa population INSEE |
| Jours de conso de la commune | `volume de pertes / volume consommé × 365` | Ratio, **propre au service** (identique pour ses communes) |
| Litres perdus/habitant/jour | `volume de pertes × 1000 / population du service / 365` | Ratio, **propre au service** |

**Hypothèses assumées :** la ventilation au prorata de la population suppose que les pertes sont
proportionnelles au nombre d'habitants (approximation : une commune étendue et peu peuplée a
proportionnellement plus de réseau). Les deux ratios sont des propriétés du réseau mutualisé :
toutes les communes d'un même service affichent la même valeur. La population vient des
**populations de référence INSEE** (millésime le plus récent), avec repli sur la population SISPEA
si l'INSEE manque ; couverture métropole + Corse (pas les DOM, absents de la carte).

> **À lire avec le rendement.** Le « litres perdus/habitant/jour » peut être élevé sans que le
> réseau soit mal entretenu : un réseau rural très étendu (des centaines de mètres de canalisation
> par habitant) affiche mécaniquement beaucoup de pertes par tête, même avec un bon rendement. La
> conformité au décret (ci-dessous), qui intègre la densité du réseau via l'ILC, est le meilleur
> juge d'un gaspillage réellement anormal.

## Rattachement au réseau de distribution

Une commune peut relever de plusieurs services (par ex. un service de **production** régional +
son service de **distribution** local). Les fuites du robinet se jouent sur la **distribution** —
et c'est aussi ce que vise le décret. Le pipeline ne retient donc que les services de distribution
(`Distribution = 1`), sans quoi une grande ville dotée d'un syndicat de production afficherait le
rendement quasi parfait de la production au lieu des pertes réelles de son réseau.

## Conformité au décret « fuites » (2012-97)

Le [décret n°2012-97](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000025208197) impose un plan
d'action quand le rendement passe sous un **rendement-seuil** :

```
rendement_seuil = min( 85 ,  65 + 0,2 × ILC )
→ conforme si rendement du réseau (P104.3) ≥ rendement_seuil
```

L'**ILC** (indice linéaire de consommation) est la variable SISPEA `VP.224`, dont on a vérifié
qu'elle correspond bien à la définition du décret — ventes d'eau à d'autres services **incluses**
au numérateur (contrôlé sur les services exportateurs). Le seuil est plafonné à 85 % et abaissé
pour les réseaux ruraux à faible ILC, conformément à l'intention du texte.

**Limite assumée :** le terme fixe 65 est appliqué à tous. Le décret prévoit 70 pour les services
prélevant plus de 2 M m³/an en zone de répartition des eaux (ZRE), critère non reconstituable ici.
Le seuil est donc **légèrement sous-estimé** pour ces rares cas, ce qui rend le verdict **prudent**
(jamais « non conforme » à tort pour cause de ZRE). Le statut par commune est
`conforme` / `non conforme` / `non calculable`, et affiché comme **indicatif**.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
navigateur. Chaque commune est colorée selon son **statut de conformité au décret « fuites »**
(vert = conforme, rouge = non conforme, gris = non calculable), avec le rendement, les équivalents
et le détail au survol. Colorer par conformité plutôt que par rendement brut évite de pointer à
tort les réseaux ruraux étendus (rendement modeste mais conforme au vu de leur faible ILC).

La carte nationale utilise la version simplifiée des contours (~19 Mo) pour rester fluide : elle
couvre la métropole (Corse comprise) mais pas les DOM, dont les communes restent présentes dans le
CSV sans apparaître sur la carte. Le fichier de contours est mis en cache dans `.cache/` après le
premier téléchargement.

Cette carte folium est pratique en local mais lourde (~30 Mo, tout le GeoJSON embarqué dans le
HTML) — trop pour une mise en ligne.

### 2 bis. Carte web légère (publiable)

```bash
npm install -g mapshaper   # prérequis (Node.js)
source .venv/bin/activate
python carte_web.py        # -> docs/carte/communes.topojson + data.json
```

Pour la publication, `carte_web.py` produit une carte optimisée : géométrie **simplifiée**
(Mapshaper, Visvalingam, topologie préservée) et encodée en **TopoJSON** (frontières partagées
stockées une fois), plus un `data.json` compact séparé (meilleur cache, moins de poids). La page
`docs/carte/index.html` (Leaflet + topojson-client) charge les deux.

Poids : ~7 Mo bruts mais **~2 Mo réellement transférés** (GitHub Pages sert en gzip), contre 30 Mo
pour la version folium. La géométrie a un plancher incompressible (~5 Mo bruts / 1,3 Mo gzip) car
les 34 000 communes sont toutes préservées (aucune supprimée par la simplification).

Les fichiers CSV et HTML générés localement ne sont pas versionnés (voir `.gitignore`), à
l'exception du site `docs/` publié pour GitHub Pages.

### 3. Exporter des CSV réutilisables

```bash
source .venv/bin/activate

python export.py --all              # national + un CSV par département -> exports/
python export.py --departement 35   # un seul département
python export.py --commune 35238    # une commune + les autres communes de son service
```

Ces exports sont pensés pour un usage associatif/militant : colonnes lisibles, arrondis, et
surtout **traçabilité** (source SISPEA, Licence Ouverte 2.0, millésime, date de génération et lien
méthodologie en tête de chaque fichier), pour qu'un fichier transmis à un tiers prouve son origine.

- **Format** : séparateur `;`, décimale `,`, encodage UTF-8 avec BOM → ouverture directe dans
  Excel FR par double-clic. Les lignes de métadonnées en tête sont préfixées par `#`.
- **Colonne « Donnée suspecte »** : marquée `oui` si le rendement est ≤ 0 % ou > 100 %, si l'avis
  qualité SISPEA est « Anomalie » / « Présomption d'anomalie », ou si un volume de base manque. Ces
  lignes ne sont pas supprimées (transparence) mais ne doivent pas être citées comme des mesures
  fiables. L'avis « Non vérifié » (donnée récente non encore validée) n'est **pas** suspect en soi.
  Le CSV national est trié par code INSEE : la première ligne n'est jamais une donnée aberrante.
- Un `LISEZMOI.txt` récapitulant source, licence, format, colonnes et règle « donnée suspecte »
  accompagne les exports.
- Les exports (~8 Mo) sont régénérables et non versionnés. Pour un site statique (GitHub Pages),
  ils seraient publiés comme fichiers pré-générés téléchargeables (pas de backend nécessaire).
