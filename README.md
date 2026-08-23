# Carnet de cuisson

Carnet de cuisine familial dédié à l'expérimentation de cuissons à l'Airfryer :
on crée un plat, on enregistre chaque essai (température, durée, note,
commentaire), on garde tout l'historique et on désigne soi-même la meilleure
combinaison.

Spécification : `testcuisson_specification.md`. Plan d'implémentation : `PLAN.md`.

## Stack

Django 6.1, Python 3.12, uv, django-environ, HTMX, sqlite en développement,
MySQL/MariaDB en production (o2switch).

## Installation

```bash
uv sync
cp .env.exemple .env
```

Générer une clé secrète et la placer dans `DJANGO_SECRET_KEY` :

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Puis :

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

## Tests

```bash
uv run python manage.py test
```

Le lanceur `config.runner.CoureurDeTests` bascule sur un hachage de mot de
passe rapide pendant les tests, ce qui ramène la suite de deux minutes à
environ une seconde. La production garde le hachage sécurisé de Django.

Jeu de données de démonstration pour le développement local :

```bash
uv run python manage.py donnees_demo
```

## Structure

| Dossier | Rôle |
|---|---|
| `config/` | Réglages, urls racine, WSGI |
| `users/` | Modèle Utilisateur, authentification par email, profil |
| `plats/` | Plats, catégories, essais de cuisson, favoris, recettes |
| `principal/` | Accueil, tableau de bord |
| `templates/` | Tous les gabarits, un sous-dossier par application |
| `static/` | CSS, police Inter, HTMX vendorisé |
| `medias/` | Fichiers envoyés par les utilisateurs (hors dépôt) |

Les gabarits sont **centralisés à la racine** plutôt que dispersés dans chaque
application : un seul endroit où chercher un écran.

```text
templates/
├── base.html
├── partiels/     # fragments partagés
├── users/
├── plats/
│   └── partiels/ # fragments propres à l'application
└── principal/
```

## Déploiement (o2switch)

La configuration est entièrement pilotée par les variables d'environnement,
aucun code métier ne change entre développement et production.

1. Créer la base MySQL et son utilisateur dédié depuis cPanel.
2. Renseigner `.env` sur le serveur : `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL=mysql://utilisateur:motdepasse@localhost:3306/base`,
   `DJANGO_STATIC_ROOT`, `DJANGO_MEDIA_ROOT`.
3. `pip install -r requirements.txt` (ou `uv export`) dans l'environnement Setup Python App.
4. `python manage.py migrate`
5. `python manage.py collectstatic`
6. `python manage.py createsuperuser`
7. Pointer le point d'entrée WSGI sur `config/wsgi.py`, puis redémarrer l'application.

Le pilote MySQL est fourni par `pymysql`, activé automatiquement dans
`config/__init__.py`.
