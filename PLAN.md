# Plan d'implémentation — Carnet de cuisson Airfryer

Document de travail dérivé de `testcuisson_specification.md`.
État actuel du dépôt : `django-admin startproject config .` seulement (Django 6.1, Python 3.12, uv). Aucun commit.

---

## 1. Architecture retenue

### 1.1 Applications

| App | Rôle |
|---|---|
| `config` | Réglages, urls racine, wsgi (déjà présent) |
| `users` | Custom User Model, authentification email, profil |
| `plats` | Plats, catégories, tests de cuisson, favoris, ingrédients, étapes |
| `principal` | Accueil, tableau de bord, `base.html`, gabarits partagés, tags/filtres communs |

### 1.2 Arborescence cible

```
config/
    settings.py          # piloté par environ
    urls.py
    wsgi.py              # + shim pymysql
users/
    models.py            # Utilisateur, GestionnaireUtilisateur
    forms.py             # InscriptionForm, ConnexionForm, ProfilForm
    views.py             # CBV auth
    urls.py
    admin.py
plats/
    models.py            # Categorie, Plat, TestCuisson, Favori, Ingredient, EtapePreparation
    managers.py          # PlatQuerySet (recherche, filtres)
    forms.py             # PlatForm, TestCuissonForm, FiltrePlatForm
    views.py
    services.py          # copier_plat(), adapter_quantites()
    mixins.py            # ProprietaireRequisMixin, PlatProprietaireRequisMixin
    urls.py
    admin.py
principal/
    views.py             # Accueil, TableauDeBord
    urls.py
templates/
    base.html
    partials/            # fragments HTMX
    users/  plats/  principal/
static/
    css/  js/  vendor/htmx.min.js
medias/                  # uploads (hors git)
.env / .env.exemple
```

---

## 2. Modèle de données

### 2.1 `users.Utilisateur`

`AbstractBaseUser` + `PermissionsMixin`.

| Champ | Type | Notes |
|---|---|---|
| `email` | EmailField unique | `USERNAME_FIELD` |
| `prenom` | CharField(blank=True) | facultatif |
| `nom` | CharField(blank=True) | facultatif |
| `is_active` | Boolean(default=True) | nom imposé par Django, libellé "compte actif" |
| `is_staff` | Boolean(default=False) | nom imposé par Django, accès admin |
| `date_inscription` | DateTimeField(auto_now_add) | |

`GestionnaireUtilisateur(BaseUserManager)` avec `creer_utilisateur()` / `creer_superutilisateur()`.
`REQUIRED_FIELDS = []`. `AUTH_USER_MODEL = "users.Utilisateur"` **avant la première migration**.

### 2.2 `plats.Categorie`

| Champ | Type |
|---|---|
| `nom` | CharField unique |
| `slug` | SlugField unique |
| `est_active` | Boolean(default=True) |
| `ordre` | PositiveSmallInteger |

Alimentée par une migration de données (Viande, Poisson, Accompagnement, Surgelé, Apéritif, Dessert, Légumes).
Voir §6, point 1 : arbitrage à faire entre modèle et `TextChoices`.

### 2.3 `plats.Plat`

| Champ | Type | Notes |
|---|---|---|
| `proprietaire` | FK Utilisateur, CASCADE, `related_name="plats"` | |
| `nom` | CharField | |
| `slug` | SlugField | unique par propriétaire |
| `description` | TextField(blank) | |
| `image` | ImageField(blank, upload_to="plats/%Y/%m") | Pillow requis |
| `categories` | M2M Categorie(blank) | |
| `nombre_personnes` | PositiveSmallInteger(default=4) | base des recettes |
| `temps_preparation_minutes` | PositiveSmallInteger(null) | |
| `meilleur_test` | FK TestCuisson, null, SET_NULL, `related_name="+"` | garantit l'unicité |
| `plat_origine` | FK "self", null, SET_NULL, `related_name="copies"` | traçabilité de la copie |
| `date_creation` / `date_modification` | | |

Contraintes : `UniqueConstraint(proprietaire, slug)`, index sur `nom` et `date_creation`.

### 2.4 `plats.TestCuisson`

| Champ | Type | Notes |
|---|---|---|
| `plat` | FK Plat, CASCADE, `related_name="tests"` | |
| `temperature_celsius` | PositiveSmallInteger | validateurs 40–260 |
| `duree_minutes` | PositiveSmallInteger | toujours en minutes |
| `note` | PositiveSmallInteger, choices 1→5 | étoiles |
| `commentaire` | TextField(blank) | |
| `date_test` | DateField(default=aujourd'hui) | |
| `date_creation` | DateTimeField(auto_now_add) | |

`Meta.ordering = ["-date_test", "-id"]`. Propriété `est_meilleur` → `self.plat.meilleur_test_id == self.pk`.
Aucun booléen "meilleur" sur le test : l'unicité vient du FK côté `Plat` (§6, point 3).

### 2.5 `plats.Favori`

`utilisateur` FK, `plat` FK, `date_ajout`, `UniqueConstraint(utilisateur, plat)`.
Modèle explicite plutôt qu'un M2M nu, pour pouvoir dater et étendre.

### 2.6 Recettes (structure posée en phase 3, remplie en phase 8)

- `Ingredient` : `plat` FK, `nom`, `quantite` Decimal(null), `unite` (TextChoices : g, kg, ml, cl, l, cuillère…), `ordre`.
- `EtapePreparation` : `plat` FK, `ordre`, `texte`.
- Adaptation des quantités : fonction pure `adapter_quantites(plat, nombre_personnes_cible)` dans `services.py`, aucun champ dénormalisé.

### 2.7 Commentaires (futur)

Aucun modèle en v1. Le `related_name="commentaires"` reste libre sur `Plat` ; l'ajout ultérieur ne touchera pas les modèles existants.

---

## 3. Vues, permissions et HTMX

### 3.1 Sécurité

- `LoginRequiredMixin` sur toute vue d'écriture.
- `ProprietaireRequisMixin` : filtre le `get_queryset()` sur `proprietaire=self.request.user` (404 plutôt que 403, on ne révèle rien).
- `PlatProprietaireRequisMixin` : pour les tests de cuisson, contrôle `plat.proprietaire`.
- La vérification se fait dans le queryset, jamais uniquement dans le gabarit.
- Admin protégé par `is_staff`, jamais accordé aux comptes familiaux.

### 3.2 Vues principales (toutes CBV)

| URL | Vue | Type |
|---|---|---|
| `/` | Accueil | TemplateView |
| `/tableau-de-bord/` | TableauDeBord | TemplateView |
| `/plats/` | ListePlats | ListView + filtres |
| `/plats/creer/` | CreerPlat | CreateView |
| `/plats/<user>/<slug>/` | DetailPlat | DetailView |
| `/plats/<user>/<slug>/modifier/` | ModifierPlat | UpdateView |
| `/plats/<user>/<slug>/supprimer/` | SupprimerPlat | DeleteView |
| `/plats/<...>/copier/` | CopierPlat | View (POST) |
| `/plats/<...>/tests/ajouter/` | CreerTest | CreateView |
| `/tests/<pk>/modifier/` | ModifierTest | UpdateView |
| `/tests/<pk>/supprimer/` | SupprimerTest | DeleteView |
| `/tests/<pk>/definir-meilleur/` | DefinirMeilleurTest | View (POST, HTMX) |
| `/plats/<...>/comparer/` | ComparerTests | ListView filtrée sur `?test=` |
| `/favoris/` | ListeFavoris | ListView |
| `/plats/<...>/favori/` | BasculerFavori | View (POST, HTMX) |
| `/compte/...` | inscription, connexion, déconnexion, profil, mot de passe | CBV Django + custom |

### 3.3 Recherche et filtres

- `FiltrePlatForm` (non lié à un modèle) : `q`, `categories`, `duree_max`, `preparation_max`, `proprietaire`, `favoris_uniquement`.
- `PlatQuerySet` avec méthodes chaînables : `.recherche(q)`, `.par_categories(...)`, `.duree_cuisson_max(n)`, `.avec_meilleur_test()`.
- Une seule vue sert la page complète et le fragment : si `request.headers.get("HX-Request")`, on rend `partials/liste_plats.html`, sinon la page entière.
- Barre de recherche : `hx-get`, `hx-trigger="keyup changed delay:300ms, search"`, `hx-target="#resultats"`, `hx-push-url="true"`.

### 3.4 Usages HTMX prévus

Recherche live, filtres combinés, bascule favori (le bouton renvoie son propre fragment), définition du meilleur test, messages Django dans une zone `hx-swap-oob`.
JavaScript maison : uniquement le menu mobile et l'aperçu d'image avant envoi. HTMX vendorisé dans `static/vendor/`, pas de CDN.

---

## 4. Configuration et déploiement

### 4.1 Dépendances à ajouter (`uv add`)

`django-environ`, `Pillow`, `pymysql` (prod), `whitenoise` (statics chez o2switch).

### 4.2 Variables d'environnement (`.env`, jamais commité ; `.env.exemple` commité)

`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`, réglages email.
`DATABASE_URL` : `sqlite:///db.sqlite3` en local, `mysql://user:mdp@localhost/base` en production. Aucun code métier ne change.

### 4.3 o2switch

- `config/wsgi.py` (ou `passenger_wsgi.py`) : shim `pymysql.install_as_MySQLdb()` tel que décrit dans la spec.
- `manage.py migrate`, `collectstatic`, `createsuperuser` documentés dans le README.
- `MEDIA_ROOT` hors du dépôt, sauvegardé séparément.
- Point de vigilance : vérifier que la version Python disponible chez o2switch supporte Django 6.1.

### 4.4 Localisation

`LANGUAGE_CODE = "fr-fr"`, `TIME_ZONE = "Europe/Paris"`, `USE_TZ = True`.

---

## 5. Découpage des lots (un lot = un commit vérifiable)

État : lots 0 à 7 réalisés, 209 tests automatisés au vert.

**Lot 0 [fait] — Fondations** (spec phase 1)
Dépendances, `environ` + `.env`, langue/fuseau, `templates/` et `static/` dans les settings, `base.html` + HTMX, `.gitignore` complet, premier commit.

**Lot 1 [fait] — Utilisateurs** (phases 1-2)
App `users`, `Utilisateur` + gestionnaire, `AUTH_USER_MODEL`, **première migration**, backend email, inscription/connexion/déconnexion/mot de passe oublié/profil, admin utilisateur, tests.
Migration à faire avant tout autre modèle : y revenir après coup est douloureux.

**Lot 2 [fait] — Plats et catégories** (phase 3)
Modèles `Categorie` + `Plat`, migration de données des catégories, CRUD complet avec contrôle de propriété, images, liste et détail, admin, tests de permissions.

**Lot 3 [fait] — Tests de cuisson** (phase 4)
Modèle `TestCuisson`, CRUD, historique sur la fiche plat, note en étoiles, définition manuelle du meilleur test, tests automatisés (dont : supprimer un test ne casse pas le plat, l'historique est préservé).

**Lot 4 [fait] — Recherche, filtres, accueil** (phase 5)
`PlatQuerySet`, `FiltrePlatForm`, fragments HTMX, page d'accueil (plats avec meilleure combinaison, récents, mieux notés), tests des filtres combinés.

**Lot 5 [fait] — Comparaison** (phase 6)
Sélection multiple de tests d'un même plat, tableau comparatif, mise en évidence du meilleur, garde-fou : tous les tests comparés doivent appartenir au même plat.

**Lot 6 [fait] — Favoris et copie** (phase 7)
`Favori` + bascule HTMX, liste des favoris, `copier_plat()` en service testé, `plat_origine`.

**Lot 7 [fait] — Recettes** (phase 8)
`Ingredient`, `EtapePreparation`, formsets inline, affichage recette, `adapter_quantites()`.

**Lot 8 — Finitions**
Vérification `manage.py check --deploy`, README de déploiement, jeu de données de démonstration, passage de relais au design.

Les lots 0 à 3 constituent la première version réellement utilisable.

---

## 6. Arbitrages validés

1. **Catégories** : modèle `Categorie` pré-rempli par migration de données. Retenu pour l'évolutivité et la gestion dans l'admin.
2. **Copie d'un plat** : on copie le plat, ses catégories, son image et sa future recette. Les tests de cuisson ne sont pas copiés. Le champ `plat_origine` garde la trace de la provenance.
3. **Meilleure combinaison** : FK `meilleur_test` sur `Plat`. Un plat désigne au plus un meilleur test, et chaque plat a le sien. L'unicité est structurelle.
4. **Filtre durée** : le filtre "temps de cuisson" porte sur la durée du meilleur test du plat. Les plats sans meilleur test désigné sont exclus quand ce filtre est actif.
5. **App utilisateurs** : nommée `users` (exception assumée à la règle du code en français, c'est l'habitude du projet). Les modèles et champs à l'intérieur restent en français : `Utilisateur`, `GestionnaireUtilisateur`.
6. **Tests** : `TestCase` Django natif, aucune dépendance supplémentaire.
7. **Champs du contrat Django** : `is_active`, `is_staff`, `is_superuser`, ainsi que `create_user` / `create_superuser`, gardent leur nom anglais. Django et son administration s'appuient dessus par nom ; les renommer obligerait à des propriétés de compatibilité fragiles. Leurs libellés affichés sont en français, et des alias `creer_utilisateur` / `creer_superutilisateur` existent pour le code du projet. Tout le reste est en français.
