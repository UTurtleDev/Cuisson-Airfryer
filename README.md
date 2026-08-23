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
| `media/` | Fichiers envoyés par les utilisateurs (hors dépôt) |

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

### Étapes

1. Créer la base MySQL et son utilisateur dédié depuis cPanel.
2. Déposer le projet, puis créer `.env` **sur le serveur** (jamais versionné) :

   ```ini
   DJANGO_SECRET_KEY=<une chaîne aléatoire de 50 caractères ou plus>
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=mon-domaine.fr,www.mon-domaine.fr
   DATABASE_URL=mysql://utilisateur:motdepasse@localhost:3306/base
   DJANGO_STATIC_ROOT=/home/COMPTE/DOMAINE/staticfiles
   DJANGO_MEDIA_ROOT=/home/COMPTE/DOMAINE/media
   DJANGO_URL_ADMINISTRATION=une-adresse-a-vous/
   ```

   Les noms de variables sont préfixés `DJANGO_` et la base passe par une seule
   `DATABASE_URL`, contrairement au découpage `DB_NAME` / `DB_USER` d'autres
   projets. Le fichier `.env.exemple` du dépôt fait référence.

3. `pip install -r requirements.txt` dans l'environnement Setup Python App.
4. `python manage.py migrate`
5. `python manage.py collectstatic`
6. `python manage.py createsuperuser`
7. Redémarrer l'application.

L'ordre compte : sans `collectstatic`, le manifeste des fichiers statiques
n'existe pas et **toutes** les pages renvoient une erreur 500, pas seulement un
affichage dégradé.

### passenger_wsgi.py

```python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

### .htaccess

La racine du projet est aussi la racine web. Sans règles explicites, `.env`,
`config/settings.py` et la base SQLite de développement seraient
**téléchargeables par n'importe qui**, puisque la règle de réécriture sert
directement tout fichier existant.

```apache
PassengerEnabled On
PassengerAppRoot /home/COMPTE/DOMAINE
PassengerPython /home/COMPTE/DOMAINE/.venv/bin/python

# --- Protection des fichiers du projet ---
# À placer avant les règles de réécriture.
<FilesMatch "\.(env|sqlite3|md|log|toml|lock|cfg|ini)$">
    Require all denied
</FilesMatch>

<FilesMatch "\.py$">
    Require all denied
</FilesMatch>

# Passenger a besoin d'atteindre ce point d'entrée.
<Files "passenger_wsgi.py">
    Require all granted
</Files>

RedirectMatch 404 /\.git
RedirectMatch 404 /\.venv

# --- Fichiers statiques servis par Apache ---
<IfModule mod_rewrite.c>
    RewriteEngine On

    # /static/... pointe vers le dossier collecté par collectstatic.
    RewriteRule ^static/(.*)$ staticfiles/$1 [L]

    # Un fichier ou dossier existant est servi tel quel.
    RewriteCond %{REQUEST_FILENAME} -f [OR]
    RewriteCond %{REQUEST_FILENAME} -d
    RewriteRule ^ - [L]

    # Tout le reste part vers Django.
    RewriteRule ^(.*)$ passenger_wsgi.py [QSA,L]
</IfModule>

<IfModule mod_mime.c>
    AddType text/css .css
    AddType application/javascript .js
    AddType image/svg+xml .svg
    AddType font/woff2 .woff2
</IfModule>
```

**Après avoir posé ces règles, vérifier deux choses :** que le site répond
toujours, et que `https://mon-domaine.fr/.env` renvoie bien une erreur 403 et
non le contenu du fichier.

Les blocs `<Directory>` ne sont pas acceptés dans un `.htaccess` : Apache ne les
autorise que dans la configuration du serveur. Pour désactiver Passenger sur un
dossier, on place un `.htaccess` contenant `PassengerEnabled off` **dans ce
dossier**.

Le pilote MySQL est fourni par `pymysql`, activé automatiquement dans
`config/__init__.py`.

### Vérifications avant mise en ligne

Avec les variables de production renseignées :

```bash
uv run python manage.py check --deploy
```

En production, `DEBUG=False` active la redirection HTTPS, les cookies sécurisés,
HSTS, et fait passer les fichiers statiques par le stockage à empreinte de
WhiteNoise.
