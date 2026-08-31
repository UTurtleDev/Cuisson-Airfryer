"""
Réglages Django du projet Cuisson.

Toute la configuration sensible ou dépendante de l'environnement est lue
depuis les variables d'environnement (fichier .env en développement).
Voir .env.exemple pour la liste des variables attendues.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# Le pilote MySQL est adapté dans config/__init__.py, exécuté avant ce
# fichier : inutile de le refaire ici.

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(str(BASE_DIR / ".env"))


# Sécurité

SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env("DJANGO_DEBUG")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# Applications

APPLICATIONS_DJANGO = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

APPLICATIONS_PROJET = [
    "principal",
    "users",
    "plats",
]

INSTALLED_APPS = APPLICATIONS_DJANGO + APPLICATIONS_PROJET

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# En développement, django.contrib.staticfiles sert déjà les fichiers :
# WhiteNoise n'est ajouté qu'en production.
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

# Adresse de l'administration : modifiable par variable d'environnement
# pour ne pas exposer /admin/ en production.
URL_ADMINISTRATION = env("DJANGO_URL_ADMINISTRATION", default="admin/")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Tous les gabarits du projet vivent dans templates/, avec un
        # sous-dossier par application. APP_DIRS reste actif pour que
        # l'administration de Django trouve les siens.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Base de données
#
# Une variable par information, plutôt qu'une URL unique : c'est plus lisible
# dans un .env, et surtout le mot de passe n'a aucun caractère à encoder.
#
# Développement : rien à écrire, sqlite par défaut.
# Production    : USE_MYSQL=True et les variables DB_*.
#
# En production, sqlite est refusé. Sans ce garde-fou, une variable oubliée
# ferait basculer le site sur une base créée au passage, vide et invisible,
# pendant que la vraie resterait inutilisée.

if env.bool("USE_MYSQL", default=False):
    DATABASES = {
        "default": {
            "ENGINE": env("DB_ENGINE", default="django.db.backends.mysql"),
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", default="localhost"),
            "PORT": env("DB_PORT", default="3306"),
            "OPTIONS": {
                # utf8mb4 pour que les accents et les caractères spéciaux
                # traversent la base sans dommage.
                "charset": "utf8mb4",
                # Le mode strict n'est pas actif par défaut chez o2switch.
                # Sans lui, MariaDB tronque une valeur trop longue au lieu
                # de refuser l'enregistrement, et ne le dit à personne.
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(
        "Base de données non configurée. En production, renseignez USE_MYSQL=True "
        "ainsi que DB_NAME, DB_USER et DB_PASSWORD dans le fichier .env."
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Validation des mots de passe

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalisation

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = "Europe/Paris"

USE_I18N = True

USE_TZ = True


# Fichiers statiques et médias

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env.path("DJANGO_STATIC_ROOT", default=BASE_DIR / "staticfiles")

MEDIA_URL = "media/"
MEDIA_ROOT = env.path("DJANGO_MEDIA_ROOT", default=BASE_DIR / "media")

# Le stockage à manifeste de WhiteNoise impose un collectstatic préalable :
# on le réserve à la production.
STOCKAGE_STATIQUES = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": STOCKAGE_STATIQUES,
    },
}


# Courriels
# En développement les messages sont affichés dans la console.
# En production, renseigner DJANGO_EMAIL_* pour passer en SMTP.

BACKEND_COURRIEL = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

OPTIONS_COURRIEL = {}
if BACKEND_COURRIEL.endswith("smtp.EmailBackend"):
    OPTIONS_COURRIEL = {
        "host": env("DJANGO_EMAIL_HOST"),
        "port": env.int("DJANGO_EMAIL_PORT", default=587),
        "username": env("DJANGO_EMAIL_USERNAME", default=""),
        "password": env("DJANGO_EMAIL_PASSWORD", default=""),
        "use_tls": env.bool("DJANGO_EMAIL_USE_TLS", default=True),
    }

MAILERS = {
    "default": {
        "BACKEND": BACKEND_COURRIEL,
        "OPTIONS": OPTIONS_COURRIEL,
    },
}

DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="cuisson@localhost")


# Tests

TEST_RUNNER = "config.runner.CoureurDeTests"


# Authentification

AUTH_USER_MODEL = "users.Utilisateur"

LOGIN_URL = "users:connexion"
LOGIN_REDIRECT_URL = "principal:tableau_de_bord"
LOGOUT_REDIRECT_URL = "principal:accueil"
