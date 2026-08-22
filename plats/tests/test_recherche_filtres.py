from django.test import TestCase
from django.urls import reverse

from plats.models import Categorie
from plats.tests.fabriques import creer_membre, creer_plat, creer_test


class RechercheEtFiltresTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")

        self.viande = Categorie.objects.get(nom="Viande")
        self.surgele = Categorie.objects.get(nom="Surgelé")

        self.hamburger = creer_plat(
            self.membre, nom="Hamburger", description="Pain, steak, cheddar"
        )
        self.hamburger.categories.add(self.viande)
        self.hamburger.definir_meilleur_test(creer_test(self.hamburger, duree=12))

        self.onion = creer_plat(self.autre, nom="Onion rings", temps_preparation_minutes=5)
        self.onion.categories.add(self.surgele)
        self.onion.definir_meilleur_test(creer_test(self.onion, duree=8))

        self.poulet = creer_plat(self.membre, nom="Poulet entier")
        self.poulet.categories.add(self.viande)
        self.poulet.definir_meilleur_test(creer_test(self.poulet, duree=45))

        self.client.force_login(self.membre)

    def resultats(self, **parametres):
        reponse = self.client.get(reverse("plats:liste"), parametres)
        self.assertEqual(reponse.status_code, 200)
        return list(reponse.context["plats"])

    def test_sans_filtre_tous_les_plats(self):
        self.assertEqual(len(self.resultats()), 3)

    def test_recherche_textuelle(self):
        self.assertEqual(self.resultats(q="burger"), [self.hamburger])

    def test_recherche_dans_la_description(self):
        self.assertEqual(self.resultats(q="cheddar"), [self.hamburger])

    def test_recherche_insensible_a_la_casse(self):
        self.assertEqual(self.resultats(q="HAMBURGER"), [self.hamburger])

    def test_filtre_categorie(self):
        resultats = self.resultats(categories=[self.viande.pk])
        self.assertCountEqual(resultats, [self.hamburger, self.poulet])

    def test_filtre_duree_de_la_meilleure_combinaison(self):
        resultats = self.resultats(duree_maximum=20)
        self.assertCountEqual(resultats, [self.hamburger, self.onion])

    def test_filtre_temps_de_preparation(self):
        self.assertEqual(self.resultats(preparation_maximum=10), [self.onion])

    def test_filtre_mes_plats(self):
        resultats = self.resultats(membre="moi")
        self.assertCountEqual(resultats, [self.hamburger, self.poulet])

    def test_filtre_sur_un_autre_membre(self):
        self.assertEqual(self.resultats(membre=self.autre.pk), [self.onion])

    def test_filtre_membre_vide_ne_filtre_rien(self):
        self.assertEqual(len(self.resultats(membre="")), 3)

    def test_filtres_combines(self):
        """Recherche + catégorie + durée, l'exemple de la spécification."""
        resultats = self.resultats(
            q="hamburger", categories=[self.viande.pk], duree_maximum=20
        )
        self.assertEqual(resultats, [self.hamburger])

    def test_filtres_combines_sans_resultat(self):
        resultats = self.resultats(
            q="hamburger", categories=[self.surgele.pk], duree_maximum=20
        )
        self.assertEqual(resultats, [])

    def test_filtre_avec_meilleure_combinaison(self):
        sans_meilleur = creer_plat(self.membre, nom="Gnocchi")
        creer_test(sans_meilleur)
        resultats = self.resultats(avec_meilleure_combinaison="on")
        self.assertNotIn(sans_meilleur, resultats)
        self.assertEqual(len(resultats), 3)

    def test_filtre_invalide_ignore_sans_erreur(self):
        reponse = self.client.get(reverse("plats:liste"), {"duree_maximum": "abc"})
        self.assertEqual(reponse.status_code, 200)


class RechercheHtmxTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        creer_plat(self.membre, nom="Hamburger")
        creer_plat(self.membre, nom="Onion rings")
        self.client.force_login(self.membre)

    def test_reponse_htmx_limitee_au_fragment(self):
        reponse = self.client.get(
            reverse("plats:liste"), {"q": "burger"}, headers={"HX-Request": "true"}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'id="resultats"')
        self.assertContains(reponse, "Hamburger")
        self.assertNotContains(reponse, "<!DOCTYPE html>")
        self.assertNotContains(reponse, "Onion rings")

    def test_page_complete_hors_htmx(self):
        reponse = self.client.get(reverse("plats:liste"), {"q": "burger"})
        self.assertContains(reponse, "<!DOCTYPE html>")
        self.assertContains(reponse, 'class="filtres"')

    def test_criteres_conserves_dans_le_formulaire(self):
        reponse = self.client.get(reverse("plats:liste"), {"q": "burger"})
        self.assertEqual(reponse.context["formulaire_filtres"]["q"].value(), "burger")


class PaginationTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        for numero in range(15):
            creer_plat(self.membre, nom=f"Plat {numero}")
        self.client.force_login(self.membre)

    def test_premiere_page(self):
        reponse = self.client.get(reverse("plats:liste"))
        self.assertEqual(len(reponse.context["plats"]), 12)
        self.assertTrue(reponse.context["is_paginated"])

    def test_seconde_page(self):
        reponse = self.client.get(reverse("plats:liste"), {"page": 2})
        self.assertEqual(len(reponse.context["plats"]), 3)

    def test_pagination_conserve_les_criteres(self):
        reponse = self.client.get(reverse("plats:liste"), {"q": "Plat 1"})
        # Plat 1, 10, 11, 12, 13, 14 : six résultats, une seule page.
        self.assertEqual(len(reponse.context["plats"]), 6)
        self.assertFalse(reponse.context["is_paginated"])


class CompteurResultatsTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        for numero in range(6):
            creer_plat(self.membre, nom=f"Plat {numero}")
        self.client.force_login(self.membre)

    def test_compteur_sans_filtre(self):
        reponse = self.client.get(reverse("plats:liste"))
        self.assertContains(reponse, "6 plats")

    def test_compteur_apres_filtre(self):
        reponse = self.client.get(reverse("plats:liste"), {"q": "Plat 3"})
        self.assertContains(reponse, "1 plat")
        self.assertNotContains(reponse, "1 plats")

    def test_compteur_sans_resultat(self):
        reponse = self.client.get(reverse("plats:liste"), {"q": "inexistant"})
        self.assertContains(reponse, "0 plat")
        self.assertNotContains(reponse, "0 plats")

    def test_compteur_total_et_non_taille_de_page(self):
        """Avec 15 plats et 12 par page, le compteur annonce bien 15."""
        for numero in range(9):
            creer_plat(self.membre, nom=f"Autre {numero}")
        reponse = self.client.get(reverse("plats:liste"))
        self.assertContains(reponse, "15 plats")
        self.assertEqual(len(reponse.context["plats"]), 12)

    def test_compteur_en_htmx(self):
        reponse = self.client.get(
            reverse("plats:liste"), {"q": "Plat"}, headers={"HX-Request": "true"}
        )
        self.assertContains(reponse, "6 plats")

    def test_compteur_sur_mes_plats(self):
        reponse = self.client.get(reverse("plats:mes_plats"))
        self.assertContains(reponse, "6 plats")


class ListeDeroulanteMembresTest(TestCase):
    def setUp(self):
        self.membre = creer_membre("sebastien@exemple.fr", prenom="Sébastien", nom="Martin")
        self.claire = creer_membre("claire@exemple.fr", prenom="Claire", nom="Martin")
        self.sans_plat = creer_membre("lucas@exemple.fr", prenom="Lucas")
        creer_plat(self.membre, nom="Hamburger")
        creer_plat(self.claire, nom="Gnocchi")
        self.client.force_login(self.membre)

    def choix(self):
        reponse = self.client.get(reverse("plats:liste"))
        return reponse.context["formulaire_filtres"].fields["membre"].choices

    def test_premier_choix_tous_les_membres(self):
        self.assertEqual(self.choix()[0], ("", "Tous les membres"))

    def test_second_choix_mes_plats(self):
        self.assertEqual(self.choix()[1], ("moi", "Seulement mes plats"))

    def test_les_autres_membres_sont_proposes(self):
        libelles = [libelle for _, libelle in self.choix()]
        self.assertIn("Claire Martin", libelles)

    def test_le_membre_connecte_n_apparait_pas_deux_fois(self):
        libelles = [libelle for _, libelle in self.choix()]
        self.assertNotIn("Sébastien Martin", libelles)

    def test_membre_sans_plat_absent(self):
        libelles = [libelle for _, libelle in self.choix()]
        self.assertNotIn("Lucas", libelles)

    def test_membre_desactive_absent(self):
        self.claire.is_active = False
        self.claire.save()
        libelles = [libelle for _, libelle in self.choix()]
        self.assertNotIn("Claire Martin", libelles)

    def test_liste_deroulante_presente_dans_la_page(self):
        reponse = self.client.get(reverse("plats:liste"))
        self.assertContains(reponse, '<select name="membre"')
        self.assertContains(reponse, "Claire Martin")
        self.assertNotContains(reponse, "Seulement mes plats</label>")

    def test_filtrage_par_un_autre_membre_depuis_la_page(self):
        reponse = self.client.get(reverse("plats:liste"), {"membre": self.claire.pk})
        # On vise les liens des plats : le mot « Hamburger » apparaît aussi
        # dans le texte indicatif du champ de recherche.
        self.assertContains(reponse, 'href="/plats/gnocchi/"')
        self.assertNotContains(reponse, 'href="/plats/hamburger/"')
        self.assertContains(reponse, "1 plat")
