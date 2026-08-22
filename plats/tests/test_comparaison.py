from datetime import date

from django.test import TestCase
from django.urls import reverse

from plats.tests.fabriques import creer_membre, creer_plat, creer_test


class NumerotationEssaisTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.plat = creer_plat(self.membre)
        self.premier = creer_test(self.plat, temperature=180, date_test=date(2026, 1, 10))
        self.deuxieme = creer_test(self.plat, temperature=190, date_test=date(2026, 2, 10))
        self.troisieme = creer_test(self.plat, temperature=200, date_test=date(2026, 3, 10))

    def test_le_premier_essai_porte_le_numero_un(self):
        numeros = {test.pk: test.numero for test in self.plat.tests_numerotes()}
        self.assertEqual(numeros[self.premier.pk], 1)
        self.assertEqual(numeros[self.deuxieme.pk], 2)
        self.assertEqual(numeros[self.troisieme.pk], 3)

    def test_affichage_du_plus_recent_au_plus_ancien(self):
        tests = self.plat.tests_numerotes()
        self.assertEqual([test.numero for test in tests], [3, 2, 1])

    def test_la_meilleure_combinaison_s_affiche_en_premier(self):
        self.plat.definir_meilleur_test(self.deuxieme)
        tests = self.plat.tests_numerotes()
        self.assertEqual(tests[0], self.deuxieme)

    def test_les_numeros_ne_changent_pas_avec_le_classement(self):
        """Remonter la meilleure en tête ne renumérote pas les essais."""
        self.plat.definir_meilleur_test(self.deuxieme)
        numeros = {test.pk: test.numero for test in self.plat.tests_numerotes()}
        self.assertEqual(numeros[self.premier.pk], 1)
        self.assertEqual(numeros[self.deuxieme.pk], 2)
        self.assertEqual(numeros[self.troisieme.pk], 3)

    def test_les_autres_essais_gardent_leur_ordre(self):
        self.plat.definir_meilleur_test(self.deuxieme)
        tests = self.plat.tests_numerotes()
        self.assertEqual([test.numero for test in tests], [2, 3, 1])


class ComparaisonTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nom="Hamburger")
        self.t1 = creer_test(
            self.plat, temperature=180, duree=12, note=2, commentaire="Trop peu cuit",
            date_test=date(2026, 1, 10),
        )
        self.t2 = creer_test(
            self.plat, temperature=180, duree=15, note=4, commentaire="Très bon",
            date_test=date(2026, 2, 10),
        )
        self.t3 = creer_test(
            self.plat, temperature=190, duree=12, note=5, commentaire="Excellent",
            date_test=date(2026, 3, 10),
        )
        self.url = reverse("plats:comparer", args=[self.plat.slug])
        self.client.force_login(self.membre)

    def comparer(self, *tests, **options):
        return self.client.get(self.url, {"test": [test.pk for test in tests]}, **options)

    def test_connexion_requise(self):
        self.client.logout()
        reponse = self.client.get(self.url)
        self.assertEqual(reponse.status_code, 302)

    def test_comparaison_de_deux_essais(self):
        reponse = self.comparer(self.t1, self.t3)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.context["tests"]), [self.t1, self.t3])
        self.assertContains(reponse, "Comparaison de 2 essais")

    def test_ordre_chronologique_dans_le_tableau(self):
        reponse = self.comparer(self.t3, self.t1, self.t2)
        self.assertEqual([test.numero for test in reponse.context["tests"]], [1, 2, 3])

    def test_essai_d_un_autre_plat_ignore(self):
        autre_plat = creer_plat(self.membre, nom="Onion rings")
        etranger = creer_test(autre_plat)
        reponse = self.comparer(self.t1, self.t2, etranger)
        self.assertEqual(list(reponse.context["tests"]), [self.t1, self.t2])
        self.assertNotIn(etranger, reponse.context["tests"])

    def test_identifiant_fantaisiste_ignore(self):
        reponse = self.client.get(self.url, {"test": ["abc", str(self.t1.pk), "999999"]})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(list(reponse.context["tests"]), [self.t1])

    def test_selection_insuffisante(self):
        reponse = self.comparer(self.t1)
        self.assertTrue(reponse.context["selection_insuffisante"])
        self.assertContains(reponse, "au moins 2 essais")
        self.assertNotContains(reponse, "tableau-comparaison")

    def test_selection_vide(self):
        reponse = self.client.get(self.url)
        self.assertEqual(reponse.context["tests"], [])
        self.assertContains(reponse, "Aucun essai sélectionné")

    def test_note_la_plus_haute_signalee(self):
        reponse = self.comparer(self.t1, self.t2)
        self.assertEqual(reponse.context["note_maximum"], 4)

    def test_meilleure_combinaison_mise_en_evidence(self):
        self.plat.definir_meilleur_test(self.t2)
        reponse = self.comparer(self.t1, self.t2, self.t3)
        self.assertContains(reponse, "test--meilleur")
        self.assertContains(reponse, "Meilleure combinaison retenue")

    def test_la_comparaison_ne_designe_pas_le_meilleur(self):
        """Comparer met en avant la meilleure note, sans rien décider."""
        self.comparer(self.t1, self.t2, self.t3)
        self.plat.refresh_from_db()
        self.assertIsNone(self.plat.meilleur_test)

    def test_un_autre_membre_peut_comparer(self):
        """Les plats sont visibles de tous : la comparaison aussi."""
        self.client.force_login(self.autre)
        reponse = self.comparer(self.t1, self.t3)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.context["tests"]), 2)

    def test_plat_inexistant(self):
        reponse = self.client.get(reverse("plats:comparer", args=["plat-fantome"]))
        self.assertEqual(reponse.status_code, 404)


class ComparaisonHtmxTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.plat = creer_plat(self.membre)
        self.t1 = creer_test(self.plat, temperature=180, date_test=date(2026, 1, 10))
        self.t2 = creer_test(self.plat, temperature=190, date_test=date(2026, 2, 10))
        self.client.force_login(self.membre)

    def test_reponse_limitee_au_fragment(self):
        reponse = self.client.get(
            reverse("plats:comparer", args=[self.plat.slug]),
            {"test": [self.t1.pk, self.t2.pk]},
            headers={"HX-Request": "true"},
        )
        self.assertContains(reponse, 'id="comparaison"')
        self.assertContains(reponse, "tableau-comparaison")
        self.assertNotContains(reponse, "<!DOCTYPE html>")

    def test_page_complete_hors_htmx(self):
        reponse = self.client.get(
            reverse("plats:comparer", args=[self.plat.slug]),
            {"test": [self.t1.pk, self.t2.pk]},
        )
        self.assertContains(reponse, "<!DOCTYPE html>")


class SelectionDepuisHistoriqueTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre)
        self.test = creer_test(self.plat)

    def test_cases_a_cocher_presentes_pour_tous(self):
        """Comparer est une lecture : ouvert à tous les membres connectés."""
        self.client.force_login(self.autre)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertContains(reponse, 'name="test"')
        self.assertContains(reponse, "Comparer les essais cochés")

    def test_zone_de_comparaison_unique(self):
        self.client.force_login(self.membre)
        contenu = self.client.get(self.plat.get_absolute_url()).content.decode()
        self.assertEqual(contenu.count('id="comparaison"'), 1)

    def test_fragment_historique_sans_zone_de_comparaison(self):
        """Le swap HTMX de l'historique ne doit pas dupliquer la zone."""
        self.client.force_login(self.membre)
        reponse = self.client.post(
            reverse("plats:definir_meilleur_test", args=[self.test.pk]),
            headers={"HX-Request": "true"},
        )
        self.assertNotContains(reponse, 'id="comparaison"')
