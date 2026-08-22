from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from plats.models import Categorie, Plat, TestCuisson
from plats.services import CopieImpossible, copier_plat
from plats.tests.fabriques import creer_membre, creer_plat, creer_test

# Une image PNG minimale valide, pour ne pas dépendre d'un fichier externe.
PNG_MINIMAL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)


class ServiceCopieTest(TestCase):
    def setUp(self):
        self.auteur = creer_membre("auteur@exemple.fr")
        self.copieur = creer_membre("copieur@exemple.fr")
        self.plat = creer_plat(
            self.auteur,
            nom="Hamburger",
            description="Pain, steak, cheddar",
            nombre_personnes=4,
            temps_preparation_minutes=20,
        )
        self.plat.categories.set(Categorie.objects.filter(nom__in=["Viande", "Surgelé"]))
        creer_test(self.plat, temperature=190, duree=12, note=5)
        creer_test(self.plat, temperature=180, duree=15, note=3)

    def test_la_copie_appartient_au_nouveau_membre(self):
        copie = copier_plat(self.plat, self.copieur)
        self.assertEqual(copie.proprietaire, self.copieur)
        self.assertNotEqual(copie.pk, self.plat.pk)

    def test_informations_reprises(self):
        copie = copier_plat(self.plat, self.copieur)
        self.assertEqual(copie.nom, self.plat.nom)
        self.assertEqual(copie.description, self.plat.description)
        self.assertEqual(copie.nombre_personnes, 4)
        self.assertEqual(copie.temps_preparation_minutes, 20)
        self.assertCountEqual(copie.categories.all(), self.plat.categories.all())

    def test_les_essais_ne_sont_pas_copies(self):
        """Les essais appartiennent à l'expérience de leur auteur."""
        copie = copier_plat(self.plat, self.copieur)
        self.assertEqual(copie.tests.count(), 0)
        self.assertEqual(self.plat.tests.count(), 2)

    def test_la_meilleure_combinaison_n_est_pas_reprise(self):
        self.plat.definir_meilleur_test(self.plat.tests.first())
        copie = copier_plat(self.plat, self.copieur)
        self.assertIsNone(copie.meilleur_test)

    def test_lien_vers_le_plat_d_origine(self):
        copie = copier_plat(self.plat, self.copieur)
        self.assertEqual(copie.plat_origine, self.plat)
        self.assertIn(copie, self.plat.copies.all())

    def test_slug_distinct(self):
        copie = copier_plat(self.plat, self.copieur)
        self.assertNotEqual(copie.slug, self.plat.slug)

    def test_modifier_la_copie_ne_touche_pas_l_original(self):
        copie = copier_plat(self.plat, self.copieur)
        copie.nom = "Hamburger revisité"
        copie.description = ""
        copie.categories.clear()
        copie.save()
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.nom, "Hamburger")
        self.assertEqual(self.plat.description, "Pain, steak, cheddar")
        self.assertEqual(self.plat.categories.count(), 2)

    def test_essais_de_la_copie_independants(self):
        copie = copier_plat(self.plat, self.copieur)
        creer_test(copie, temperature=200, duree=10)
        self.assertEqual(copie.tests.count(), 1)
        self.assertEqual(self.plat.tests.count(), 2)

    def test_supprimer_l_original_conserve_la_copie(self):
        copie = copier_plat(self.plat, self.copieur)
        self.plat.delete()
        copie.refresh_from_db()
        self.assertTrue(Plat.objects.filter(pk=copie.pk).exists())
        self.assertIsNone(copie.plat_origine)

    def test_copie_de_son_propre_plat_refusee(self):
        with self.assertRaises(CopieImpossible):
            copier_plat(self.plat, self.auteur)

    def test_copie_d_une_copie(self):
        troisieme = creer_membre("troisieme@exemple.fr")
        copie = copier_plat(self.plat, self.copieur)
        copie_de_copie = copier_plat(copie, troisieme)
        self.assertEqual(copie_de_copie.plat_origine, copie)
        self.assertEqual(copie_de_copie.proprietaire, troisieme)


@override_settings(MEDIA_ROOT="/tmp/cuisson-tests-medias")
class CopieImageTest(TestCase):
    def setUp(self):
        self.auteur = creer_membre("auteur@exemple.fr")
        self.copieur = creer_membre("copieur@exemple.fr")
        self.plat = creer_plat(
            self.auteur,
            nom="Hamburger",
            image=SimpleUploadedFile("burger.png", PNG_MINIMAL, content_type="image/png"),
        )

    def tearDown(self):
        import shutil

        shutil.rmtree("/tmp/cuisson-tests-medias", ignore_errors=True)

    def test_image_dupliquee_et_non_partagee(self):
        """Deux plats qui pointeraient le même fichier ne seraient pas indépendants."""
        copie = copier_plat(self.plat, self.copieur)
        self.assertTrue(copie.image)
        self.assertNotEqual(copie.image.name, self.plat.image.name)

    def test_contenu_identique(self):
        copie = copier_plat(self.plat, self.copieur)
        copie.image.open("rb")
        self.plat.image.open("rb")
        try:
            self.assertEqual(copie.image.read(), self.plat.image.read())
        finally:
            copie.image.close()
            self.plat.image.close()

    def test_plat_sans_image(self):
        sans_image = creer_plat(self.auteur, nom="Onion rings")
        copie = copier_plat(sans_image, self.copieur)
        self.assertFalse(copie.image)


class VueCopieTest(TestCase):
    def setUp(self):
        self.auteur = creer_membre("auteur@exemple.fr")
        self.copieur = creer_membre("copieur@exemple.fr")
        self.plat = creer_plat(self.auteur, nom="Hamburger")
        creer_test(self.plat)
        self.url = reverse("plats:copier", args=[self.plat.slug])

    def test_connexion_requise(self):
        reponse = self.client.post(self.url)
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Plat.objects.count(), 1)

    def test_copie_et_redirection(self):
        self.client.force_login(self.copieur)
        reponse = self.client.post(self.url)
        copie = Plat.objects.get(proprietaire=self.copieur)
        self.assertRedirects(reponse, copie.get_absolute_url())

    def test_methode_get_refusee(self):
        self.client.force_login(self.copieur)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_copie_de_son_propre_plat_refusee(self):
        self.client.force_login(self.auteur)
        reponse = self.client.post(self.url, follow=True)
        self.assertEqual(Plat.objects.count(), 1)
        self.assertContains(reponse, "vous appartient déjà")

    def test_le_bouton_copier_absent_sur_son_propre_plat(self):
        self.client.force_login(self.auteur)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertNotContains(reponse, "Copier ce plat chez moi")

    def test_le_bouton_copier_present_sur_le_plat_d_un_autre(self):
        self.client.force_login(self.copieur)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertContains(reponse, "Copier ce plat chez moi")

    def test_la_copie_ne_donne_aucun_droit_sur_l_original(self):
        self.client.force_login(self.copieur)
        self.client.post(self.url)
        reponse = self.client.post(
            reverse("plats:modifier", args=[self.plat.slug]),
            {"nom": "Detourne", "nombre_personnes": 4},
        )
        self.assertEqual(reponse.status_code, 404)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.nom, "Hamburger")

    def test_le_proprietaire_peut_modifier_sa_copie(self):
        self.client.force_login(self.copieur)
        self.client.post(self.url)
        copie = Plat.objects.get(proprietaire=self.copieur)
        reponse = self.client.post(
            reverse("plats:modifier", args=[copie.slug]),
            {"nom": "Hamburger revisité", "nombre_personnes": 4},
        )
        self.assertEqual(reponse.status_code, 302)
        copie.refresh_from_db()
        self.assertEqual(copie.nom, "Hamburger revisité")

    def test_origine_affichee_sur_la_copie(self):
        self.client.force_login(self.copieur)
        self.client.post(self.url)
        copie = Plat.objects.get(proprietaire=self.copieur)
        reponse = self.client.get(copie.get_absolute_url())
        self.assertContains(reponse, "Copié depuis")
        self.assertContains(reponse, self.auteur.nom_affiche)

    def test_aucun_essai_sur_la_copie(self):
        self.client.force_login(self.copieur)
        self.client.post(self.url)
        copie = Plat.objects.get(proprietaire=self.copieur)
        self.assertEqual(TestCuisson.objects.filter(plat=copie).count(), 0)
