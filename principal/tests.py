from django.test import TestCase
from django.urls import reverse

from plats.tests.fabriques import creer_membre, creer_plat, creer_test


class AccueilTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.plat_reussi = creer_plat(self.membre, nom="Hamburger")
        self.plat_reussi.definir_meilleur_test(creer_test(self.plat_reussi, note=5))
        self.plat_en_cours = creer_plat(self.membre, nom="Gnocchi")
        creer_test(self.plat_en_cours, note=2)

    def test_accueil_accessible_sans_connexion(self):
        reponse = self.client.get(reverse("principal:accueil"))
        self.assertEqual(reponse.status_code, 200)

    def test_aucun_plat_expose_aux_visiteurs(self):
        """Le carnet est familial : rien ne fuite avant connexion."""
        reponse = self.client.get(reverse("principal:accueil"))
        self.assertNotContains(reponse, "Hamburger")
        self.assertContains(reponse, "Se connecter")

    def test_mise_en_avant_pour_les_membres(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:accueil"))
        self.assertContains(reponse, "Cuissons au point")
        self.assertContains(reponse, "Hamburger")

    def test_plats_avec_meilleure_combinaison(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:accueil"))
        mis_en_avant = reponse.context["plats_avec_meilleure_combinaison"]
        self.assertIn(self.plat_reussi, mis_en_avant)
        self.assertNotIn(self.plat_en_cours, mis_en_avant)

    def test_classement_par_note_moyenne(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:accueil"))
        mieux_notes = list(reponse.context["plats_mieux_notes"])
        self.assertEqual(mieux_notes[0], self.plat_reussi)


class TableauDeBordTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nom="Hamburger")
        creer_test(self.plat, temperature=190)
        creer_plat(self.autre, nom="Onion rings")

    def test_inaccessible_sans_connexion(self):
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.status_code, 302)

    def test_ne_montre_que_mes_plats_et_mes_tests(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.context["nombre_de_plats"], 1)
        self.assertContains(reponse, "Hamburger")
        self.assertNotContains(reponse, "Onion rings")
        self.assertContains(reponse, "190 °C")
