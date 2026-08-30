"""Contrôles appliqués aux fichiers envoyés par les membres."""

from django.core.exceptions import ValidationError

#: Au-delà, on refuse. Une photo de téléphone récent pèse 3 à 5 Mo brute ;
#: la limite laisse donc passer un cliché normal et arrête les envois
#: manifestement disproportionnés, en attendant un vrai redimensionnement.
TAILLE_MAXIMUM_MEGAOCTETS = 5

TAILLE_MAXIMUM_OCTETS = TAILLE_MAXIMUM_MEGAOCTETS * 1024 * 1024


def valider_taille_image(fichier):
    """Refuse une image trop lourde, avec un message qui dit quoi faire.

    Le contrôle est côté serveur : l'attribut `accept` du champ de
    formulaire ne fait qu'aider au choix du fichier, il n'empêche rien.
    """
    taille = getattr(fichier, "size", None)
    if taille is None or taille <= TAILLE_MAXIMUM_OCTETS:
        return

    poids = taille / (1024 * 1024)
    raise ValidationError(
        "Cette image pèse %(poids).1f Mo, la limite est de %(limite)s Mo. "
        "Réduisez sa taille avant de l'envoyer.",
        code="image_trop_lourde",
        params={"poids": poids, "limite": TAILLE_MAXIMUM_MEGAOCTETS},
    )
