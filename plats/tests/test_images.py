"""Garde-fou sur le poids des images envoyées."""

import io
import math
import os
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from plats.images import normaliser_image
from plats.models import Plat
from plats.tests.fabriques import creer_membre
from plats.validateurs import TAILLE_MAXIMUM_OCTETS, valider_taille_image


def fichier_de(octets):
    """Un objet qui déclare un poids, sans être un vrai fichier.

    Le validateur ne regarde que la taille : l'éprouver avec un simple
    objet porteur de `size` teste la règle sans dépendre du format image.
    """
    return SimpleNamespace(size=octets)


def image_reelle_de(octets, nom="photo.png"):
    """Une vraie image PNG pesant au moins le poids demandé.

    Le bruit aléatoire ne se compresse pas : le poids du fichier suit
    donc les dimensions, ce qui permet de viser une taille.
    """
    cote = max(1, int(math.sqrt(octets / 3)) + 1)
    image = Image.frombytes("RGB", (cote, cote), os.urandom(cote * cote * 3))
    tampon = io.BytesIO()
    image.save(tampon, format="PNG", compress_level=0)
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


class ValidateurTailleTest(TestCase):
    def test_image_legere_acceptee(self):
        self.assertIsNone(valider_taille_image(fichier_de(1024)))

    def test_image_a_la_limite_acceptee(self):
        self.assertIsNone(valider_taille_image(fichier_de(TAILLE_MAXIMUM_OCTETS)))

    def test_image_trop_lourde_refusee(self):
        with self.assertRaises(ValidationError) as capture:
            valider_taille_image(fichier_de(TAILLE_MAXIMUM_OCTETS + 1))
        self.assertEqual(capture.exception.code, "image_trop_lourde")

    def test_message_indique_le_poids_et_la_limite(self):
        with self.assertRaises(ValidationError) as capture:
            valider_taille_image(fichier_de(TAILLE_MAXIMUM_OCTETS * 2))
        message = capture.exception.messages[0]
        self.assertIn("30.0 Mo", message)
        self.assertIn("15 Mo", message)

    def test_objet_sans_taille_ignore(self):
        """Un objet sans attribut size ne doit pas faire échouer le contrôle."""
        self.assertIsNone(valider_taille_image(object()))


@override_settings(MEDIA_ROOT="/tmp/cuisson-tests-images")
class EnvoiImageTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.client.force_login(self.membre)

    def tearDown(self):
        import shutil

        shutil.rmtree("/tmp/cuisson-tests-images", ignore_errors=True)

    def creer(self, image=None):
        donnees = {"nom": "Poulet au curry", "nombre_personnes": 4}
        if image is not None:
            donnees["image"] = image
        return self.client.post(reverse("plats:creer"), donnees)

    def test_photo_raisonnable_acceptee(self):
        reponse = self.creer(image_reelle_de(2 * 1024 * 1024))
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(Plat.objects.get(nom="Poulet au curry").image)

    def test_photo_trop_lourde_refusee(self):
        reponse = self.creer(image_reelle_de(TAILLE_MAXIMUM_OCTETS + 200 * 1024))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Plat.objects.filter(nom="Poulet au curry").exists())

    def test_message_affiche_a_l_utilisateur(self):
        reponse = self.creer(image_reelle_de(TAILLE_MAXIMUM_OCTETS + 200 * 1024))
        self.assertContains(reponse, "la limite est de 15")
        self.assertContains(reponse, "Réduisez sa taille")

    def test_plat_sans_image_toujours_possible(self):
        self.assertEqual(self.creer().status_code, 302)

    def test_limite_annoncee_sur_le_formulaire(self):
        contenu = self.client.get(reverse("plats:creer")).content.decode()
        self.assertIn("15 Mo maximum", contenu)
        self.assertIn('accept="image/*"', contenu)


def photo(largeur, hauteur, format="JPEG", mode="RGB", couleur=(200, 120, 60), exif=None):
    """Une image unie, aux dimensions demandées, prête à être postée.

    Une teinte unie suffit : ces tests mesurent des dimensions et un poids,
    pas un rendu.
    """
    image = Image.new(mode, (largeur, hauteur), couleur)
    tampon = io.BytesIO()
    options = {"exif": exif} if exif is not None else {}
    image.save(tampon, format=format, **options)
    extension = "jpg" if format == "JPEG" else format.lower()
    return SimpleUploadedFile(
        f"photo.{extension}", tampon.getvalue(), content_type=f"image/{extension}"
    )


class NormalisationTest(TestCase):
    """Le traitement lui-même, éprouvé sans passer par une vue."""

    def dimensions(self, fichier):
        return Image.open(io.BytesIO(normaliser_image(fichier).read())).size

    def test_grande_photo_ramenee_a_la_largeur_de_reference(self):
        self.assertEqual(self.dimensions(photo(3000, 4000)), (1000, 1250))

    def test_photo_paysage_recadree_au_ratio_d_affichage(self):
        """Le fichier porte le cadrage que la fiche montre, sans déformation."""
        self.assertEqual(self.dimensions(photo(2000, 1000)), (800, 1000))

    def test_photo_carree_recadree(self):
        self.assertEqual(self.dimensions(photo(1500, 1500)), (1000, 1250))

    def test_photo_moyenne_jamais_agrandie(self):
        """Agrandir n'ajouterait que du flou et du poids."""
        self.assertEqual(self.dimensions(photo(600, 750)), (600, 750))

    def test_orientation_exif_appliquee_aux_pixels(self):
        """Une photo de téléphone couchée doit se redresser une fois pour toutes.

        Orientation 6 : le cliché est stocké en paysage et doit être pivoté.
        Redressé, le 1400 × 700 devient un 700 × 1400 portrait, qui tient
        entier dans le cadre ; non redressé, il serait rogné à 560 × 700.
        """
        image = Image.new("RGB", (1400, 700), (10, 20, 30))
        donnees_exif = image.getexif()
        donnees_exif[274] = 6
        self.assertEqual(
            self.dimensions(photo(1400, 700, exif=donnees_exif)), (700, 875)
        )

    def test_transparence_posee_sur_du_blanc(self):
        """Le JPEG ignore l'alpha : sans fond blanc, le transparent virerait au noir."""
        resultat = normaliser_image(
            photo(600, 750, format="PNG", mode="RGBA", couleur=(0, 0, 0, 0))
        )
        image = Image.open(io.BytesIO(resultat.read()))
        self.assertEqual(image.mode, "RGB")
        rouge, vert, bleu = image.getpixel((10, 10))
        self.assertGreater(min(rouge, vert, bleu), 240)

    def test_le_fichier_rendu_est_un_jpeg(self):
        resultat = normaliser_image(photo(800, 1000, format="PNG"))
        self.assertTrue(resultat.name.endswith(".jpg"))
        self.assertEqual(Image.open(io.BytesIO(resultat.read())).format, "JPEG")

    def test_le_nom_choisi_est_conserve(self):
        fichier = photo(800, 1000, format="PNG")
        fichier.name = "gratin de courgettes.PNG"
        self.assertEqual(normaliser_image(fichier).name, "gratin de courgettes.jpg")

    def test_le_poids_fond(self):
        """L'intérêt de l'opération : une photo de téléphone qui devient légère.

        Le bruit aléatoire est le pire cas possible pour un JPEG, rien ne s'y
        compresse. Une vraie photo tombe bien plus bas ; si même ce cas-là
        passe sous le seuil, le gain est acquis.
        """
        lourde = image_reelle_de(3 * 1024 * 1024)
        allegee = normaliser_image(lourde)
        self.assertLess(allegee.size, 600 * 1024)

    def test_vignette_refusee(self):
        """Une vignette pèse trois fois rien et serait pourtant illisible.

        C'est le cas qui montre que le poids ne dit rien de la qualité :
        92 × 92 pixels passent tous les contrôles de taille de fichier.
        """
        with self.assertRaises(ValidationError) as capture:
            normaliser_image(photo(92, 92))
        self.assertEqual(capture.exception.code, "image_trop_petite")

    def test_message_du_refus_donne_les_chiffres(self):
        with self.assertRaises(ValidationError) as capture:
            normaliser_image(photo(92, 92))
        message = capture.exception.messages[0]
        self.assertIn("92 × 92", message)
        self.assertIn("560", message)

    def test_panorama_refuse_malgre_sa_largeur(self):
        """Le contrôle porte sur ce qui reste après recadrage, pas sur le brut.

        2000 pixels de large font illusion, mais au format 4/5 il n'en reste
        que 240 : la hauteur commande.
        """
        with self.assertRaises(ValidationError) as capture:
            normaliser_image(photo(2000, 300))
        self.assertEqual(capture.exception.code, "image_trop_petite")

    def test_image_juste_au_plancher_acceptee(self):
        self.assertEqual(self.dimensions(photo(560, 700)), (560, 700))

    def test_fichier_illisible_signale_proprement(self):
        casse = SimpleUploadedFile("photo.jpg", b"ceci n'est pas une image")
        with self.assertRaises(ValidationError) as capture:
            normaliser_image(casse)
        self.assertEqual(capture.exception.code, "image_illisible")


@override_settings(MEDIA_ROOT="/tmp/cuisson-tests-normalisation")
class EnvoiNormaliseTest(TestCase):
    """Le traitement vu depuis le formulaire, là où le membre l'utilise."""

    def setUp(self):
        self.membre = creer_membre()
        self.client.force_login(self.membre)

    def tearDown(self):
        import shutil

        shutil.rmtree("/tmp/cuisson-tests-normalisation", ignore_errors=True)

    def creer(self, image):
        return self.client.post(
            reverse("plats:creer"),
            {"nom": "Gratin", "nombre_personnes": 4, "image": image},
        )

    def test_image_enregistree_au_format_d_affichage(self):
        self.creer(photo(3024, 4032))
        plat = Plat.objects.get(nom="Gratin")
        self.assertEqual((plat.image.width, plat.image.height), (1000, 1250))
        self.assertTrue(plat.image.name.endswith(".jpg"))
        self.assertLess(plat.image.size, 500 * 1024)

    def test_vignette_refusee_par_le_formulaire(self):
        reponse = self.creer(photo(92, 92))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Plat.objects.filter(nom="Gratin").exists())
        self.assertContains(reponse, "serait floue à l&#x27;affichage")

    def test_minimum_annonce_sur_le_formulaire(self):
        contenu = self.client.get(reverse("plats:creer")).content.decode()
        self.assertIn("560 pixels de large", contenu)

    def test_modifier_un_plat_sans_toucher_a_la_photo_la_laisse_intacte(self):
        """Sans nouvel envoi, le champ rend le fichier déjà en base : on n'y retouche pas."""
        self.creer(photo(2000, 2500))
        plat = Plat.objects.get(nom="Gratin")
        fichier_initial = plat.image.name

        reponse = self.client.post(
            reverse("plats:modifier", kwargs={"slug": plat.slug}),
            {"nom": "Gratin de courgettes", "nombre_personnes": 4},
        )
        self.assertEqual(reponse.status_code, 302)

        plat.refresh_from_db()
        self.assertEqual(plat.image.name, fichier_initial)
