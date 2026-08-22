from django.test import TestCase
from django.urls import reverse

from plats.models import Plat, TestCuisson
from plats.tests.fabriques import creer_membre, creer_plat, creer_test


class ModeleTestCuissonTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.plat = creer_plat(self.membre)

    def test_representation(self):
        test = creer_test(self.plat, temperature=190, duree=12)
        self.assertEqual(str(test), "190 °C / 12 min")

    def test_duree_lisible_au_dela_d_une_heure(self):
        self.assertEqual(creer_test(self.plat, duree=45).duree_lisible, "45 min")
        self.assertEqual(creer_test(self.plat, duree=60).duree_lisible, "1 h")
        self.assertEqual(creer_test(self.plat, duree=75).duree_lisible, "1 h 15")

    def test_historique_conserve_les_anciens_tests(self):
        creer_test(self.plat, temperature=180, duree=12)
        creer_test(self.plat, temperature=190, duree=12)
        creer_test(self.plat, temperature=200, duree=10)
        self.assertEqual(self.plat.tests.count(), 3)

    def test_ordre_du_plus_recent_au_plus_ancien(self):
        from datetime import date

        ancien = creer_test(self.plat, date_test=date(2026, 1, 1))
        recent = creer_test(self.plat, date_test=date(2026, 6, 1))
        self.assertEqual(list(self.plat.tests.all()), [recent, ancien])


class MeilleureCombinaisonTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.plat = creer_plat(self.membre)
        self.premier = creer_test(self.plat, temperature=180, duree=12, note=2)
        self.second = creer_test(self.plat, temperature=190, duree=12, note=5)

    def test_aucune_meilleure_combinaison_par_defaut(self):
        self.assertIsNone(self.plat.meilleur_test)
        self.assertFalse(self.premier.est_meilleur)

    def test_designation_manuelle(self):
        self.plat.definir_meilleur_test(self.premier)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.meilleur_test, self.premier)

    def test_une_seule_meilleure_combinaison_a_la_fois(self):
        self.plat.definir_meilleur_test(self.premier)
        self.plat.definir_meilleur_test(self.second)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.meilleur_test, self.second)
        self.assertFalse(self.plat.tests.get(pk=self.premier.pk).est_meilleur)

    def test_la_note_ne_designe_pas_automatiquement(self):
        """La meilleure combinaison reste un choix humain, jamais déduit."""
        self.plat.definir_meilleur_test(self.premier)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.meilleur_test, self.premier)

    def test_test_d_un_autre_plat_refuse(self):
        autre_plat = creer_plat(self.membre, nom="Onion rings")
        test_etranger = creer_test(autre_plat)
        with self.assertRaises(ValueError):
            self.plat.definir_meilleur_test(test_etranger)

    def test_suppression_du_meilleur_test_conserve_le_plat(self):
        self.plat.definir_meilleur_test(self.premier)
        self.premier.delete()
        self.plat.refresh_from_db()
        self.assertIsNone(self.plat.meilleur_test)
        self.assertTrue(Plat.objects.filter(pk=self.plat.pk).exists())
        self.assertEqual(self.plat.tests.count(), 1)

    def test_chaque_plat_a_sa_propre_meilleure_combinaison(self):
        autre_plat = creer_plat(self.membre, nom="Onion rings")
        autre_test = creer_test(autre_plat, temperature=200, duree=8)
        self.plat.definir_meilleur_test(self.second)
        autre_plat.definir_meilleur_test(autre_test)
        self.plat.refresh_from_db()
        autre_plat.refresh_from_db()
        self.assertEqual(self.plat.meilleur_test, self.second)
        self.assertEqual(autre_plat.meilleur_test, autre_test)


class VuesTestCuissonTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre)
        self.test = creer_test(self.plat)

    def test_creation_par_le_proprietaire(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(
            reverse("plats:creer_test", args=[self.plat.slug]),
            {
                "temperature_celsius": 190,
                "duree_minutes": 15,
                "note": 4,
                "commentaire": "Bien doré",
                "date_test": "2026-08-22",
            },
        )
        self.assertRedirects(reponse, self.plat.get_absolute_url())
        self.assertEqual(self.plat.tests.count(), 2)

    def test_creation_refusee_sur_le_plat_d_un_autre(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(
            reverse("plats:creer_test", args=[self.plat.slug]),
            {"temperature_celsius": 190, "duree_minutes": 15, "note": 4, "date_test": "2026-08-22"},
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.plat.tests.count(), 1)

    def test_modification_refusee_a_un_autre(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(
            reverse("plats:modifier_test", args=[self.test.pk]),
            {"temperature_celsius": 250, "duree_minutes": 1, "note": 1, "date_test": "2026-08-22"},
        )
        self.assertEqual(reponse.status_code, 404)
        self.test.refresh_from_db()
        self.assertEqual(self.test.temperature_celsius, 180)

    def test_suppression_par_le_proprietaire(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(reverse("plats:supprimer_test", args=[self.test.pk]))
        self.assertRedirects(reponse, self.plat.get_absolute_url())
        self.assertFalse(TestCuisson.objects.filter(pk=self.test.pk).exists())

    def test_suppression_refusee_a_un_autre(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(reverse("plats:supprimer_test", args=[self.test.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(TestCuisson.objects.filter(pk=self.test.pk).exists())

    def test_temperature_hors_bornes_refusee(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(
            reverse("plats:creer_test", args=[self.plat.slug]),
            {"temperature_celsius": 400, "duree_minutes": 15, "note": 4, "date_test": "2026-08-22"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.plat.tests.count(), 1)


class DefinirMeilleurTestVueTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre)
        self.test = creer_test(self.plat)

    def test_designation_par_le_proprietaire(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(reverse("plats:definir_meilleur_test", args=[self.test.pk]))
        self.assertRedirects(reponse, self.plat.get_absolute_url())
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.meilleur_test, self.test)

    def test_second_appel_retire_la_designation(self):
        self.client.force_login(self.membre)
        self.client.post(reverse("plats:definir_meilleur_test", args=[self.test.pk]))
        self.client.post(reverse("plats:definir_meilleur_test", args=[self.test.pk]))
        self.plat.refresh_from_db()
        self.assertIsNone(self.plat.meilleur_test)

    def test_reponse_htmx_renvoie_le_fragment(self):
        self.client.force_login(self.membre)
        reponse = self.client.post(
            reverse("plats:definir_meilleur_test", args=[self.test.pk]),
            headers={"HX-Request": "true"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'id="historique"')
        self.assertNotContains(reponse, "<!DOCTYPE html>")

    def test_refuse_a_un_autre_membre(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(reverse("plats:definir_meilleur_test", args=[self.test.pk]))
        self.assertEqual(reponse.status_code, 404)
        self.plat.refresh_from_db()
        self.assertIsNone(self.plat.meilleur_test)

    def test_methode_get_refusee(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("plats:definir_meilleur_test", args=[self.test.pk]))
        self.assertEqual(reponse.status_code, 405)


class FiltreDureeTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.rapide = creer_plat(self.membre, nom="Onion rings")
        self.lent = creer_plat(self.membre, nom="Poulet entier")
        self.rapide.definir_meilleur_test(creer_test(self.rapide, duree=8))
        self.lent.definir_meilleur_test(creer_test(self.lent, duree=45))
        self.sans_meilleur = creer_plat(self.membre, nom="Gnocchi")
        creer_test(self.sans_meilleur, duree=5)

    def test_filtre_sur_la_duree_de_la_meilleure_combinaison(self):
        resultats = Plat.objects.duree_cuisson_maximum(20)
        self.assertIn(self.rapide, resultats)
        self.assertNotIn(self.lent, resultats)

    def test_plat_sans_meilleure_combinaison_ecarte(self):
        """Sans meilleure combinaison désignée, aucune durée ne fait référence."""
        self.assertNotIn(self.sans_meilleur, Plat.objects.duree_cuisson_maximum(20))

    def test_avec_meilleur_test(self):
        self.assertEqual(Plat.objects.avec_meilleur_test().count(), 2)


class AffichageHistoriqueTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre)
        self.test = creer_test(self.plat, temperature=190, duree=75, note=5)
        self.plat.definir_meilleur_test(self.test)

    def test_historique_visible_sur_la_fiche(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertContains(reponse, "Historique des tests")
        self.assertContains(reponse, "190 °C")
        self.assertContains(reponse, "1 h 15")
        self.assertContains(reponse, "Meilleure combinaison actuelle")

    def test_boutons_absents_pour_les_autres_membres(self):
        self.client.force_login(self.autre)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertContains(reponse, "Historique des tests")
        self.assertNotContains(reponse, "Ajouter un test de cuisson")
        self.assertNotContains(reponse, "hx-post")
