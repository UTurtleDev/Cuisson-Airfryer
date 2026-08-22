"""Petites fabriques partagées par les tests de l'application plats."""

from django.contrib.auth import get_user_model

from plats.models import Plat, TestCuisson

Utilisateur = get_user_model()


def creer_membre(email="membre@exemple.fr", **champs):
    return Utilisateur.objects.creer_utilisateur(
        email=email, mot_de_passe="MotDePasseSolide123", **champs
    )


def creer_plat(proprietaire, nom="Hamburger", **champs):
    return Plat.objects.create(proprietaire=proprietaire, nom=nom, **champs)


def creer_test(plat, temperature=180, duree=12, note=3, **champs):
    return TestCuisson.objects.create(
        plat=plat,
        temperature_celsius=temperature,
        duree_minutes=duree,
        note=note,
        **champs,
    )
