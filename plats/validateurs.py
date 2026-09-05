"""Contrôles appliqués aux fichiers envoyés par les membres."""

from django.core.exceptions import ValidationError

#: Au-delà, on refuse. La photo envoyée est de toute façon recadrée et
#: ré-encodée (voir `plats.images`), le fichier gardé ne pèse que quelques
#: centaines de kilo-octets : la limite ne protège donc plus le disque, elle
#: protège la mémoire du serveur et évite d'attendre un envoi interminable.
#: Elle est large exprès, une photo de reflex passe sans discussion.
TAILLE_MAXIMUM_MEGAOCTETS = 15

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
