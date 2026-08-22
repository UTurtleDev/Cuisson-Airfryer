"""Petites fabriques partagées par les tests de l'application plats."""

from django.contrib.auth import get_user_model

from plats.models import Plat

Utilisateur = get_user_model()


def creer_membre(email="membre@exemple.fr", **champs):
    return Utilisateur.objects.creer_utilisateur(
        email=email, mot_de_passe="MotDePasseSolide123", **champs
    )


def creer_plat(proprietaire, nom="Hamburger", **champs):
    return Plat.objects.create(proprietaire=proprietaire, nom=nom, **champs)
