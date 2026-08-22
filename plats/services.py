"""Opérations métier sur les plats.

Ces fonctions sont volontairement hors des vues : elles sont testables seules
et réutilisables depuis l'administration ou une commande.
"""

from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction


class CopieImpossible(Exception):
    """Levée quand la copie demandée n'a pas de sens."""


@transaction.atomic
def copier_plat(plat, utilisateur):
    """Crée une copie indépendante d'un plat au nom d'un autre membre.

    Ce qui est copié : le nom, la description, l'image, les catégories, les
    ingrédients et les étapes de préparation.

    Ce qui ne l'est pas : les tests de cuisson. Ils appartiennent à
    l'expérience de leur auteur, et un Airfryer ne cuit pas de la même façon
    d'une maison à l'autre. Le nouveau membre repart donc de ses propres
    essais.

    Le lien vers le plat d'origine est conservé pour l'attribution, sans
    donner le moindre droit sur celui-ci.
    """
    if plat.proprietaire_id == utilisateur.pk:
        raise CopieImpossible("Ce plat vous appartient déjà.")

    copie = plat.__class__.objects.create(
        proprietaire=utilisateur,
        nom=plat.nom,
        description=plat.description,
        nombre_personnes=plat.nombre_personnes,
        temps_preparation_minutes=plat.temps_preparation_minutes,
        plat_origine=plat,
    )
    copie.categories.set(plat.categories.all())
    copier_recette(plat, copie)

    if plat.image:
        copier_image(plat, copie)

    return copie


def copier_recette(plat, copie):
    """Duplique ingrédients et étapes, en conservant leur ordre."""
    from plats.models import EtapePreparation, Ingredient

    Ingredient.objects.bulk_create(
        [
            Ingredient(
                plat=copie,
                nom=ingredient.nom,
                quantite=ingredient.quantite,
                unite=ingredient.unite,
                ordre=ingredient.ordre,
            )
            for ingredient in plat.ingredients.all()
        ]
    )
    EtapePreparation.objects.bulk_create(
        [
            EtapePreparation(plat=copie, ordre=etape.ordre, texte=etape.texte)
            for etape in plat.etapes.all()
        ]
    )


def copier_image(plat, copie):
    """Duplique le fichier image plutôt que d'en partager un seul.

    Deux plats qui pointeraient le même fichier ne seraient pas indépendants :
    remplacer l'image de l'un changerait celle de l'autre.
    """
    plat.image.open("rb")
    try:
        copie.image.save(
            Path(plat.image.name).name, ContentFile(plat.image.read()), save=True
        )
    finally:
        plat.image.close()


def basculer_favori(plat, utilisateur):
    """Ajoute le plat aux favoris du membre, ou l'en retire. Renvoie l'état."""
    from plats.models import Favori

    favori = Favori.objects.filter(utilisateur=utilisateur, plat=plat).first()
    if favori is not None:
        favori.delete()
        return False

    Favori.objects.create(utilisateur=utilisateur, plat=plat)
    return True


def adapter_quantites(plat, nombre_personnes_cible):
    """Adapte les quantités d'un plat à un autre nombre de personnes.

    Les ingrédients reçoivent un attribut ``quantite_adaptee`` et un attribut
    ``libelle_adapte``. Le plat et ses ingrédients ne sont jamais modifiés en
    base : l'adaptation est un calcul d'affichage.

    Une quantité vide reste vide : « sel » ou « poivre » ne se multiplient pas.
    """
    from decimal import ROUND_HALF_UP, Decimal

    ingredients = list(plat.ingredients.all())

    reference = plat.nombre_personnes or 0
    if not reference or not nombre_personnes_cible or nombre_personnes_cible == reference:
        for ingredient in ingredients:
            ingredient.quantite_adaptee = ingredient.quantite
            ingredient.libelle_adapte = ingredient.libelle
        return ingredients

    facteur = Decimal(nombre_personnes_cible) / Decimal(reference)
    for ingredient in ingredients:
        if ingredient.quantite is None:
            ingredient.quantite_adaptee = None
        else:
            ingredient.quantite_adaptee = (ingredient.quantite * facteur).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        ingredient.libelle_adapte = ingredient.libelle_pour(ingredient.quantite_adaptee)
    return ingredients
