from django.test import TestCase

from plats.models import Categorie, Plat
from plats.tests.fabriques import creer_membre, creer_plat


class PlatTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()

    def test_slug_genere_depuis_le_nom(self):
        plat = creer_plat(self.membre, nom="Gnocchi au chorizo")
        self.assertEqual(plat.slug, "gnocchi-au-chorizo")

    def test_slug_unique_meme_nom_deux_membres(self):
        autre = creer_membre("autre@exemple.fr")
        premier = creer_plat(self.membre, nom="Onion rings")
        second = creer_plat(autre, nom="Onion rings")
        self.assertEqual(premier.slug, "onion-rings")
        self.assertEqual(second.slug, "onion-rings-2")

    def test_slug_conserve_a_la_modification(self):
        plat = creer_plat(self.membre, nom="Cordon bleu")
        plat.nom = "Cordon bleu maison"
        plat.save()
        self.assertEqual(plat.slug, "cordon-bleu")

    def test_categories_multiples(self):
        plat = creer_plat(self.membre)
        plat.categories.set(Categorie.objects.filter(nom__in=["Viande", "Surgelé"]))
        self.assertEqual(plat.categories.count(), 2)

    def test_appartenance(self):
        plat = creer_plat(self.membre)
        autre = creer_membre("autre@exemple.fr")
        self.assertTrue(plat.appartient_a(self.membre))
        self.assertFalse(plat.appartient_a(autre))

    def test_categories_initiales_presentes(self):
        self.assertTrue(Categorie.objects.filter(nom="Viande").exists())
        self.assertEqual(Categorie.objects.count(), 7)


class QuerySetPlatTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        creer_plat(self.membre, nom="Hamburger", description="Pain, steak")
        creer_plat(self.autre, nom="Onion rings")

    def test_de(self):
        self.assertEqual(Plat.objects.de(self.membre).count(), 1)

    def test_recherche_sur_le_nom(self):
        self.assertEqual(Plat.objects.recherche("burger").count(), 1)

    def test_recherche_sur_la_description(self):
        self.assertEqual(Plat.objects.recherche("steak").count(), 1)

    def test_recherche_vide_retourne_tout(self):
        self.assertEqual(Plat.objects.recherche("").count(), 2)
