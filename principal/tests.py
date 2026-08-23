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

    def test_bouton_de_creation_visible(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:accueil"))
        self.assertContains(reponse, "Ajouter un plat")

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

    def test_compteurs_a_l_echelle_de_la_famille(self):
        """Le tableau de bord est « le carnet en chiffres », pas un espace privé."""
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.context["nombre_de_plats"], 2)
        self.assertEqual(reponse.context["nombre_d_essais"], 1)
        self.assertEqual(reponse.context["nombre_a_regler"], 2)

    def test_au_point_compte_les_combinaisons_retenues(self):
        self.plat.definir_meilleur_test(self.plat.tests.first())
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.context["nombre_au_point"], 1)
        self.assertEqual(reponse.context["nombre_a_regler"], 1)

    def test_qui_cuisine(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        repartition = reponse.context["qui_cuisine"]
        self.assertEqual(len(repartition), 1)
        self.assertEqual(repartition[0]["total"], 1)
        self.assertEqual(repartition[0]["part"], 100)

    def test_temperatures_utilisees(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        temperatures = reponse.context["temperatures"]
        self.assertEqual(temperatures[0]["temperature_celsius"], 190)
        self.assertEqual(temperatures[0]["total"], 1)

    def test_mes_plats_reste_personnel(self):
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.context["mes_plats_total"], 1)
        self.assertEqual(list(reponse.context["mes_plats"]), [self.plat])

    def test_aucune_statistique_sans_essai(self):
        from plats.models import TestCuisson

        TestCuisson.objects.all().delete()
        self.client.force_login(self.membre)
        reponse = self.client.get(reverse("principal:tableau_de_bord"))
        self.assertEqual(reponse.context["qui_cuisine"], [])
        self.assertEqual(reponse.context["temperatures"], [])
        self.assertContains(reponse, "Aucun essai enregistré")


class GabaritsTest(TestCase):
    """Garde-fous sur l'écriture des gabarits."""

    def chemins_des_gabarits(self):
        from pathlib import Path

        from django.conf import settings

        racine = Path(settings.BASE_DIR)
        for chemin in racine.rglob("*.html"):
            if ".venv" in chemin.parts or "staticfiles" in chemin.parts:
                continue
            yield chemin

    def test_aucun_commentaire_multiligne(self):
        """{# ... #} ne tient que sur une ligne : au-delà, Django l'affiche.

        Les commentaires de plusieurs lignes doivent utiliser
        {% comment %} ... {% endcomment %}.
        """
        fautifs = []
        for chemin in self.chemins_des_gabarits():
            for numero, ligne in enumerate(chemin.read_text().splitlines(), 1):
                if "{#" in ligne and "#}" not in ligne:
                    fautifs.append(f"{chemin.name}:{numero}")
        self.assertEqual(fautifs, [], f"Commentaires multilignes à corriger : {fautifs}")


class PagesRendueTest(TestCase):
    """Vérifie qu'aucune syntaxe de gabarit ne fuit dans les pages rendues."""

    def setUp(self):
        self.membre = creer_membre()
        self.plat = creer_plat(self.membre, nom="Gnocchi au chorizo")
        creer_test(self.plat)
        self.client.force_login(self.membre)

    def pages(self):
        from django.urls import reverse

        return [
            reverse("principal:accueil"),
            reverse("principal:tableau_de_bord"),
            reverse("plats:liste"),
            reverse("plats:mes_plats"),
            self.plat.get_absolute_url(),
            reverse("plats:creer"),
            reverse("plats:creer_test", args=[self.plat.slug]),
        ]

    def test_aucune_balise_de_gabarit_affichee(self):
        for url in self.pages():
            with self.subTest(url=url):
                contenu = self.client.get(url).content.decode()
                self.assertNotIn("{#", contenu)
                self.assertNotIn("{%", contenu)
                self.assertNotIn("{{", contenu)
