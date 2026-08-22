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

    Ce qui est copié : le nom, la description, l'image, les catégories et les
    informations de recette.

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

    if plat.image:
        copier_image(plat, copie)

    return copie


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
