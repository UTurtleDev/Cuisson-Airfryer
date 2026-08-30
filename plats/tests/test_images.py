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
        self.assertIn("10.0 Mo", message)
        self.assertIn("5 Mo", message)

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
        reponse = self.creer(image_reelle_de(200 * 1024))
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(Plat.objects.get(nom="Poulet au curry").image)

    def test_photo_trop_lourde_refusee(self):
        reponse = self.creer(image_reelle_de(TAILLE_MAXIMUM_OCTETS + 200 * 1024))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Plat.objects.filter(nom="Poulet au curry").exists())

    def test_message_affiche_a_l_utilisateur(self):
        reponse = self.creer(image_reelle_de(TAILLE_MAXIMUM_OCTETS + 200 * 1024))
        self.assertContains(reponse, "la limite est de 5")
        self.assertContains(reponse, "Réduisez sa taille")

    def test_plat_sans_image_toujours_possible(self):
        self.assertEqual(self.creer().status_code, 302)

    def test_limite_annoncee_sur_le_formulaire(self):
        contenu = self.client.get(reverse("plats:creer")).content.decode()
        self.assertIn("5 Mo maximum", contenu)
        self.assertIn('accept="image/*"', contenu)
