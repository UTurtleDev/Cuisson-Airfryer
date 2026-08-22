from django.test import TestCase
from django.urls import reverse

from plats.models import Categorie, Plat
from plats.tests.fabriques import creer_membre, creer_plat


class ListeEtDetailTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nom="Hamburger")
        self.plat_autre = creer_plat(self.autre, nom="Onion rings")

    def test_liste_inaccessible_sans_connexion(self):
        reponse = self.client.get(reverse("plats:liste"))
        self.assertEqual(reponse.status_code, 302)

    def test_liste_affiche_les_plats_de_tous(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("plats:liste"))
        self.assertContains(reponse, "Hamburger")
        self.assertContains(reponse, "Onion rings")

    def test_mes_plats_ne_montre_que_les_siens(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("plats:mes_plats"))
        self.assertContains(reponse, "Hamburger")
        self.assertNotContains(reponse, "Onion rings")

    def test_detail_du_plat_d_un_autre_membre_visible(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(self.plat_autre.get_absolute_url())
        self.assertEqual(reponse.status_code, 200)

    def test_actions_masquees_sur_le_plat_d_un_autre(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(self.plat_autre.get_absolute_url())
        self.assertNotContains(reponse, "Supprimer")


class CreationTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.client.force_login(self.membre)

    def test_creation_attribue_le_proprietaire(self):
        categorie = Categorie.objects.get(nom="Viande")
        reponse = self.client.post(
            reverse("plats:creer"),
            {
                "nom": "Cordon bleu",
                "description": "Surgelé",
                "categories": [categorie.pk],
                "nombre_personnes": 4,
                "temps_preparation_minutes": "",
            },
        )
        plat = Plat.objects.get(nom="Cordon bleu")
        self.assertRedirects(reponse, plat.get_absolute_url())
        self.assertEqual(plat.proprietaire, self.membre)
        self.assertEqual(list(plat.categories.all()), [categorie])

    def test_proprietaire_non_falsifiable(self):
        """Envoyer un propriétaire dans le formulaire ne change rien."""
        victime = creer_membre("victime@exemple.fr")
        self.client.post(
            reverse("plats:creer"),
            {"nom": "Tentative", "nombre_personnes": 4, "proprietaire": victime.pk},
        )
        self.assertEqual(Plat.objects.get(nom="Tentative").proprietaire, self.membre)


class PermissionsTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nom="Hamburger")

    def test_le_proprietaire_peut_modifier(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(
            reverse("plats:modifier", args=[self.plat.slug]),
            {"nom": "Hamburger maison", "nombre_personnes": 4},
        )
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.nom, "Hamburger maison")
        self.assertRedirects(reponse, self.plat.get_absolute_url())

    def test_un_autre_membre_ne_peut_pas_modifier(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(
            reverse("plats:modifier", args=[self.plat.slug]),
            {"nom": "Detourne", "nombre_personnes": 4},
        )
        self.assertEqual(reponse.status_code, 404)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.nom, "Hamburger")

    def test_un_autre_membre_ne_peut_pas_supprimer(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(reverse("plats:supprimer", args=[self.plat.slug]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(Plat.objects.filter(pk=self.plat.pk).exists())

    def test_le_proprietaire_peut_supprimer(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(reverse("plats:supprimer", args=[self.plat.slug]))
        self.assertRedirects(reponse, reverse("plats:mes_plats"))
        self.assertFalse(Plat.objects.filter(pk=self.plat.pk).exists())

    def test_modification_impossible_sans_connexion(self):
        reponse = self.client.get(reverse("plats:modifier", args=[self.plat.slug]))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("users:connexion"), reponse.url)
