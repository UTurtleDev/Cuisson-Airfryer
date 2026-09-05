"""Mise au format des photos de plats, avant enregistrement.

Une photo arrive presque toujours d'un téléphone : 4000 pixels de large,
trois à cinq mégaoctets, orientée par une donnée EXIF plutôt que par ses
pixels. Telle quelle, elle coûte cher à stocker et à télécharger, alors que
la fiche du plat n'en affiche qu'un cadre de 280 pixels au ratio 4/5.

On la ramène donc une fois pour toutes à ce que la page montre : recadrée au
centre au ratio d'affichage, ramenée à la largeur de référence, ré-encodée
en JPEG. Le navigateur reçoit une image déjà à la bonne taille, et le disque
garde quelques centaines de kilo-octets au lieu de plusieurs mégaoctets.

C'est une opération sans retour : l'original n'est pas conservé. C'est
assumé, le site n'est pas une photothèque.
"""

import io
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

#: Ratio d'affichage de la fiche (`.photo img` dans `carnet.css`). Le
#: recadrage suit le CSS : ce que la page rogne, le fichier ne le porte pas.
RATIO_LARGEUR, RATIO_HAUTEUR = 4, 5

#: Largeur de référence. Le cadre fait 280 pixels CSS ; ces 1000 pixels
#: couvrent largement les écrans à forte densité et la version mobile, où la
#: photo passe en bandeau pleine largeur.
LARGEUR_CIBLE = 1000

#: En dessous, on refuse. Le poids du fichier ne dit rien de sa qualité : une
#: vignette de 92 pixels pèse 3 ko et passerait tous les contrôles de taille,
#: mais le navigateur devrait l'étirer trois fois pour remplir le cadre.
#:
#: Le seuil est la largeur exacte du cadre : en dessous, l'image est étirée
#: même sur un écran ordinaire, et ça se voit. Au-dessus, elle peut rester un
#: peu douce sur un écran à forte densité, et c'est accepté : la photo illustre
#: le plat, elle n'est pas là pour être scrutée. Viser le rendu parfait
#: refuserait quantité d'images correctes, notamment les carrées, qui perdent
#: un cinquième de leur largeur au recadrage.
LARGEUR_MINIMUM = 280

#: 82 est le palier où l'œil ne distingue plus la compression sur une photo
#: de cuisine, alors que le fichier a déjà fondu.
QUALITE_JPEG = 82

#: Au-delà, on refuse de décoder. Un fichier compressé de quelques Mo peut
#: cacher une image gigantesque, qui occuperait plusieurs centaines de Mo une
#: fois dépliée en mémoire.
PIXELS_MAXIMUM = 50_000_000


def normaliser_image(fichier):
    """Renvoie une nouvelle image, recadrée, redimensionnée et ré-encodée.

    Le fichier reçu n'est pas modifié : la fonction rend un fichier neuf,
    prêt à être posé sur le champ `image` du plat.
    """
    fichier.seek(0)
    try:
        with Image.open(fichier) as source:
            verifier_le_nombre_de_pixels(source)
            image = ImageOps.exif_transpose(source)
            image = aplatir(image)
            cible = dimensions_cibles(image)
            verifier_la_finesse(cible, image.size)
            image = ImageOps.fit(image, cible, method=Image.Resampling.LANCZOS)
            contenu = encoder(image)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erreur:
        raise ValidationError(
            "Cette image n'a pas pu être lue. Réessayez avec un fichier JPEG ou PNG.",
            code="image_illisible",
        ) from erreur

    return SimpleUploadedFile(nom_jpeg(fichier.name), contenu, content_type="image/jpeg")


def verifier_le_nombre_de_pixels(image):
    """Arrête les images démesurées avant que Pillow ne les déplie."""
    largeur, hauteur = image.size
    if largeur * hauteur > PIXELS_MAXIMUM:
        raise ValidationError(
            "Cette image fait %(largeur)s × %(hauteur)s pixels, c'est trop grand "
            "pour être traité.",
            code="image_trop_grande",
            params={"largeur": largeur, "hauteur": hauteur},
        )


def verifier_la_finesse(cible, taille_source):
    """Refuse une image trop petite pour le cadre de la fiche.

    Le contrôle porte sur ce qu'il reste **après** recadrage : une photo
    panoramique très large peut être grande et ne rien laisser une fois
    ramenée au format 4/5.

    On refuse plutôt que d'agrandir : un agrandissement ne rend pas les
    détails absents, il les invente en flou, et le membre ne comprendrait pas
    pourquoi sa fiche est laide alors que l'envoi a été accepté.
    """
    largeur_utile, _ = cible
    if largeur_utile >= LARGEUR_MINIMUM:
        return

    largeur, hauteur = taille_source
    raise ValidationError(
        "Cette image fait %(largeur)s × %(hauteur)s pixels. Recadrée au format "
        "de la fiche il n'en resterait que %(utile)s pixels de large, elle "
        "serait floue à l'affichage. Il en faut au moins %(minimum)s.",
        code="image_trop_petite",
        params={
            "largeur": largeur,
            "hauteur": hauteur,
            "utile": largeur_utile,
            "minimum": LARGEUR_MINIMUM,
        },
    )


def aplatir(image):
    """Ramène l'image en RVB, sur fond blanc si elle est transparente.

    Le JPEG ne connaît pas la transparence : une conversion directe poserait
    les zones transparentes sur du noir. Le fond blanc est plus proche de ce
    que l'auteur du fichier voyait.
    """
    transparente = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    if not transparente:
        return image.convert("RGB")

    image = image.convert("RGBA")
    fond = Image.new("RGB", image.size, "white")
    fond.paste(image, mask=image.getchannel("A"))
    return fond


def dimensions_cibles(image):
    """Taille finale de l'image : au ratio d'affichage, jamais agrandie.

    On part du plus grand rectangle 4/5 qui tient dans la photo, puis on le
    ramène à la largeur de référence. Une photo déjà petite garde sa taille :
    l'agrandir n'inventerait que du flou et du poids.
    """
    largeur, hauteur = image.size
    if largeur * RATIO_HAUTEUR > hauteur * RATIO_LARGEUR:
        # Photo plus large que le cadre : la hauteur commande.
        largeur_disponible = hauteur * RATIO_LARGEUR // RATIO_HAUTEUR
    else:
        largeur_disponible = largeur

    largeur_finale = max(1, min(LARGEUR_CIBLE, largeur_disponible))
    hauteur_finale = max(1, round(largeur_finale * RATIO_HAUTEUR / RATIO_LARGEUR))
    return largeur_finale, hauteur_finale


def encoder(image):
    """Écrit l'image en JPEG progressif, sans les métadonnées d'origine.

    Rien de l'EXIF n'est recopié : l'orientation a déjà été appliquée aux
    pixels, et les coordonnées GPS d'une photo de cuisine n'ont pas à se
    retrouver en ligne.
    """
    tampon = io.BytesIO()
    image.save(
        tampon,
        format="JPEG",
        quality=QUALITE_JPEG,
        optimize=True,
        progressive=True,
    )
    return tampon.getvalue()


def nom_jpeg(nom):
    """Garde le nom choisi par le membre, en corrigeant l'extension."""
    base = Path(nom or "photo").name
    return f"{Path(base).stem or 'photo'}.jpg"
