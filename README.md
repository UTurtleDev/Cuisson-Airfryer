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
   DJANGO_ALLOWED_HOSTS=mon-domaine.fr
   DJANGO_STATIC_ROOT=/home/COMPTE/DOMAINE/staticfiles
   DJANGO_MEDIA_ROOT=/home/COMPTE/DOMAINE/media
   DJANGO_URL_ADMINISTRATION=une-adresse-a-vous/

   USE_MYSQL=True
   DB_NAME=COMPTE_nomdelabase
   DB_USER=COMPTE_utilisateur
   DB_PASSWORD=le-mot-de-passe-tel-quel
   DB_HOST=localhost
   DB_PORT=3306
   ```

   Une variable par information plutôt qu'une URL de connexion : c'est plus
   lisible, et le mot de passe n'a aucun caractère à encoder. cPanel préfixe
   le nom de la base et celui de l'utilisateur avec l'identifiant du compte.

   En production, sqlite est **refusé** : sans `USE_MYSQL=True` et les
   variables `DB_*`, le démarrage échoue avec un message explicite au lieu de
   basculer en silence sur une base créée au passage.

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

**cPanel écrit son propre bloc Passenger** dans le `.htaccess` de la racine,
entre deux lignes « DO NOT REMOVE ». Ce bloc porte le chemin de l'application et
l'interpréteur de l'environnement virtuel créé par cPanel, qui se trouve sous
`/home/COMPTE/virtualenv/...` et non dans le `.venv` du projet. Il ne faut pas
le remplacer : les règles du projet viennent en dessous.

```apache
# ... bloc CLOUDLINUX PASSENGER CONFIGURATION généré par cPanel ...

<IfModule mod_autoindex.c>
    Options -Indexes
</IfModule>

<FilesMatch "\.(env|py|sqlite3|md|log|toml|lock|cfg|ini|yml|yaml)$">
    Require all denied
</FilesMatch>

RedirectMatch 404 /\.git
RedirectMatch 404 /\.venv

<IfModule mod_mime.c>
    AddType text/css .css
    AddType application/javascript .js
    AddType image/svg+xml .svg
    AddType font/woff2 .woff2
</IfModule>
```

Aucune règle de réécriture : Passenger prend en charge toutes les requêtes de
l'application. Une règle du type « si le fichier existe, sers-le » est même
nuisible ici, car elle publie le code source dès que Passenger ne démarre pas.

Les fichiers statiques sont servis par WhiteNoise, à l'intérieur de Django.

**Si la page affiche le contenu de `passenger_wsgi.py`**, Passenger n'a pas pris
la main : vérifier la présence du bloc cPanel, le chemin de `PassengerPython`,
le démarrage de l'application, puis le journal indiqué par
`PassengerAppLogFile`.

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
