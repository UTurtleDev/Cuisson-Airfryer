from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from plats.models import EtapePreparation, Ingredient
from plats.services import adapter_quantites
from plats.tests.fabriques import creer_membre, creer_plat


def creer_ingredient(plat, nom="Farine", quantite="250", unite="g", ordre=1):
    return Ingredient.objects.create(
        plat=plat,
        nom=nom,
        quantite=Decimal(quantite) if quantite is not None else None,
        unite=unite,
        ordre=ordre,
    )


class LibelleIngredientTest(TestCase):
    def setUp(self):
        self.plat = creer_plat(creer_membre())

    def test_avec_unite(self):
        ingredient = creer_ingredient(self.plat, "farine", "250", "g")
        self.assertEqual(ingredient.libelle, "250 g de farine")

    def test_sans_unite(self):
        ingredient = creer_ingredient(self.plat, "œufs", "2", "")
        self.assertEqual(ingredient.libelle, "2 œufs")

    def test_sans_quantite(self):
        ingredient = creer_ingredient(self.plat, "sel", None, "")
        self.assertEqual(ingredient.libelle, "sel")

    def test_decimales_inutiles_supprimees(self):
        ingredient = creer_ingredient(self.plat, "farine", "250.00", "g")
        self.assertEqual(ingredient.libelle, "250 g de farine")

    def test_decimale_utile_conservee(self):
        ingredient = creer_ingredient(self.plat, "lait", "0.75", "l")
        self.assertEqual(ingredient.libelle, "0,75 l de lait")

    def test_unite_affichee_en_toutes_lettres(self):
        ingredient = creer_ingredient(self.plat, "huile", "2", "cs")
        self.assertEqual(ingredient.libelle, "2 cuillère à soupe d'huile")


class AdaptationQuantitesTest(TestCase):
    def setUp(self):
        self.plat = creer_plat(creer_membre(), nombre_personnes=4)
        self.farine = creer_ingredient(self.plat, "farine", "250", "g", ordre=1)
        self.oeufs = creer_ingredient(self.plat, "œufs", "2", "", ordre=2)
        self.sel = creer_ingredient(self.plat, "sel", None, "", ordre=3)

    def quantites(self, personnes):
        return {
            ingredient.nom: ingredient.quantite_adaptee
            for ingredient in adapter_quantites(self.plat, personnes)
        }

    def test_adaptation_a_la_hausse(self):
        """Recette pour 4 adaptée pour 6, l'exemple de la spécification."""
        self.assertEqual(self.quantites(6)["farine"], Decimal("375.00"))
        self.assertEqual(self.quantites(6)["œufs"], Decimal("3.00"))

    def test_adaptation_a_la_baisse(self):
        self.assertEqual(self.quantites(2)["farine"], Decimal("125.00"))

    def test_meme_nombre_ne_change_rien(self):
        self.assertEqual(self.quantites(4)["farine"], Decimal("250"))

    def test_quantite_libre_non_multipliee(self):
        """« sel » ou « poivre » ne se multiplient pas."""
        self.assertIsNone(self.quantites(10)["sel"])

    def test_arrondi_au_centieme(self):
        self.assertEqual(self.quantites(3)["farine"], Decimal("187.50"))

    def test_libelle_adapte(self):
        ingredients = {i.nom: i for i in adapter_quantites(self.plat, 6)}
        self.assertEqual(ingredients["farine"].libelle_adapte, "375 g de farine")
        self.assertEqual(ingredients["sel"].libelle_adapte, "sel")

    def test_rien_n_est_enregistre_en_base(self):
        """L'adaptation est un calcul d'affichage, pas une modification."""
        adapter_quantites(self.plat, 12)
        self.farine.refresh_from_db()
        self.assertEqual(self.farine.quantite, Decimal("250"))

    def test_nombre_de_personnes_absent(self):
        self.assertEqual(self.quantites(None)["farine"], Decimal("250"))


class AffichageRecetteTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nombre_personnes=4)
        creer_ingredient(self.plat, "farine", "250", "g")
        EtapePreparation.objects.create(plat=self.plat, ordre=1, texte="Mélanger.")
        self.client.force_login(self.membre)

    def test_recette_sur_la_fiche_du_plat(self):
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertContains(reponse, "250 g de farine")
        self.assertContains(reponse, "Mélanger.")

    def test_plat_sans_recette(self):
        vide = creer_plat(self.membre, nom="Onion rings")
        reponse = self.client.get(vide.get_absolute_url())
        self.assertContains(reponse, "Aucune recette n'est encore écrite")

    def test_lien_de_modification_reserve_au_proprietaire(self):
        self.client.force_login(self.autre)
        reponse = self.client.get(self.plat.get_absolute_url())
        self.assertNotContains(reponse, "Modifier la recette")

    def test_adaptation_par_l_url(self):
        reponse = self.client.get(
            reverse("plats:recette", args=[self.plat.slug]), {"personnes": 6}
        )
        self.assertContains(reponse, "375 g de farine")
        self.assertContains(reponse, "quantités recalculées")

    def test_adaptation_en_htmx(self):
        reponse = self.client.get(
            reverse("plats:recette", args=[self.plat.slug]),
            {"personnes": 8},
            headers={"HX-Request": "true"},
        )
        self.assertContains(reponse, 'id="recette"')
        self.assertContains(reponse, "500 g de farine")
        self.assertNotContains(reponse, "<!DOCTYPE html>")

    def test_nombre_de_personnes_invalide_ignore(self):
        reponse = self.client.get(
            reverse("plats:recette", args=[self.plat.slug]), {"personnes": "beaucoup"}
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "250 g de farine")

    def test_recette_visible_par_les_autres_membres(self):
        self.client.force_login(self.autre)
        reponse = self.client.get(reverse("plats:recette", args=[self.plat.slug]))
        self.assertContains(reponse, "250 g de farine")


class ModifierRecetteTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nombre_personnes=4)
        self.url = reverse("plats:modifier_recette", args=[self.plat.slug])
        self.client.force_login(self.membre)

    def donnees(self, **remplacements):
        donnees = {
            "ingredients-TOTAL_FORMS": "3",
            "ingredients-INITIAL_FORMS": "0",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-nom": "Farine",
            "ingredients-0-quantite": "250",
            "ingredients-0-unite": "g",
            "ingredients-1-nom": "Œufs",
            "ingredients-1-quantite": "2",
            "ingredients-1-unite": "",
            "ingredients-2-nom": "",
            "ingredients-2-quantite": "",
            "ingredients-2-unite": "",
            "etapes-TOTAL_FORMS": "2",
            "etapes-INITIAL_FORMS": "0",
            "etapes-MIN_NUM_FORMS": "0",
            "etapes-MAX_NUM_FORMS": "1000",
            "etapes-0-texte": "Mélanger la farine et les œufs.",
            "etapes-1-texte": "Cuire 12 minutes.",
        }
        donnees.update(remplacements)
        return donnees

    def test_enregistrement(self):
        reponse = self.client.post(self.url, self.donnees())
        self.assertRedirects(reponse, self.plat.get_absolute_url())
        self.assertEqual(self.plat.ingredients.count(), 2)
        self.assertEqual(self.plat.etapes.count(), 2)

    def test_ligne_vide_ignoree(self):
        self.client.post(self.url, self.donnees())
        self.assertFalse(self.plat.ingredients.filter(nom="").exists())

    def test_ordre_suit_la_position_dans_la_page(self):
        self.client.post(self.url, self.donnees())
        ingredients = list(self.plat.ingredients.all())
        self.assertEqual([i.nom for i in ingredients], ["Farine", "Œufs"])
        self.assertEqual([i.ordre for i in ingredients], [1, 2])

    def test_ordre_des_etapes(self):
        self.client.post(self.url, self.donnees())
        etapes = list(self.plat.etapes.all())
        self.assertEqual(etapes[0].texte, "Mélanger la farine et les œufs.")
        self.assertEqual([e.ordre for e in etapes], [1, 2])

    def test_donnees_invalides_reaffichent_le_formulaire(self):
        reponse = self.client.post(
            self.url, self.donnees(**{"ingredients-0-quantite": "-5"})
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.plat.ingredients.count(), 0)

    def test_reserve_au_proprietaire(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(self.url, self.donnees())
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(self.plat.ingredients.count(), 0)

    def test_connexion_requise(self):
        self.client.logout()
        reponse = self.client.get(self.url)
        self.assertEqual(reponse.status_code, 302)

    def test_suppression_d_une_ligne(self):
        self.client.post(self.url, self.donnees())
        farine = self.plat.ingredients.get(nom="Farine")
        oeufs = self.plat.ingredients.get(nom="Œufs")
        self.client.post(
            self.url,
            {
                "ingredients-TOTAL_FORMS": "2",
                "ingredients-INITIAL_FORMS": "2",
                "ingredients-MIN_NUM_FORMS": "0",
                "ingredients-MAX_NUM_FORMS": "1000",
                "ingredients-0-id": str(farine.pk),
                "ingredients-0-nom": "Farine",
                "ingredients-0-quantite": "250",
                "ingredients-0-unite": "g",
                "ingredients-0-DELETE": "on",
                "ingredients-1-id": str(oeufs.pk),
                "ingredients-1-nom": "Œufs",
                "ingredients-1-quantite": "2",
                "ingredients-1-unite": "",
                "etapes-TOTAL_FORMS": "0",
                "etapes-INITIAL_FORMS": "0",
                "etapes-MIN_NUM_FORMS": "0",
                "etapes-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(self.plat.ingredients.count(), 1)
        self.assertEqual(self.plat.ingredients.first().nom, "Œufs")


class RecetteEtCopieTest(TestCase):
    def test_la_recette_suit_la_copie(self):
        from plats.services import copier_plat

        auteur = creer_membre("auteur@exemple.fr")
        copieur = creer_membre("copieur@exemple.fr")
        plat = creer_plat(auteur, nombre_personnes=4)
        creer_ingredient(plat, "farine", "250", "g")
        EtapePreparation.objects.create(plat=plat, ordre=1, texte="Mélanger.")

        copie = copier_plat(plat, copieur)
        self.assertEqual(copie.ingredients.count(), 1)
        self.assertEqual(copie.etapes.count(), 1)
        self.assertEqual(copie.ingredients.first().libelle, "250 g de farine")

    def test_recette_de_la_copie_independante(self):
        from plats.services import copier_plat

        auteur = creer_membre("auteur@exemple.fr")
        copieur = creer_membre("copieur@exemple.fr")
        plat = creer_plat(auteur, nombre_personnes=4)
        creer_ingredient(plat, "farine", "250", "g")

        copie = copier_plat(plat, copieur)
        copie.ingredients.all().delete()

        self.assertEqual(plat.ingredients.count(), 1)
        self.assertEqual(copie.ingredients.count(), 0)

    def test_ordre_de_la_recette_conserve(self):
        from plats.services import copier_plat

        auteur = creer_membre("auteur@exemple.fr")
        copieur = creer_membre("copieur@exemple.fr")
        plat = creer_plat(auteur)
        creer_ingredient(plat, "farine", "250", "g", ordre=1)
        creer_ingredient(plat, "sucre", "100", "g", ordre=2)

        copie = copier_plat(plat, copieur)
        self.assertEqual([i.nom for i in copie.ingredients.all()], ["farine", "sucre"])


class AccesRecetteTest(TestCase):
    """La recette doit être atteignable sans chercher dans la page."""

    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.membre, nom="Hamburger")
        self.client.force_login(self.membre)

    def contenu(self, plat=None):
        return self.client.get((plat or self.plat).get_absolute_url()).content.decode()

    def test_lien_ajouter_une_recette_dans_les_actions(self):
        self.assertIn("Ajouter une recette", self.contenu())

    def test_lien_present_deux_fois_actions_et_bloc_recette(self):
        """Une entrée dans la barre d'actions, une dans le bloc recette vide."""
        url = reverse("plats:modifier_recette", args=[self.plat.slug])
        self.assertEqual(self.contenu().count(url), 2)

    def test_le_libelle_devient_modifier_quand_la_recette_existe(self):
        creer_ingredient(self.plat, "farine", "250", "g")
        contenu = self.contenu()
        self.assertIn("Modifier la recette", contenu)
        self.assertNotIn("Ajouter une recette", contenu)

    def test_aucun_lien_de_recette_pour_les_autres_membres(self):
        self.client.force_login(self.autre)
        contenu = self.contenu()
        self.assertNotIn("Ajouter une recette", contenu)
        self.assertNotIn(reverse("plats:modifier_recette", args=[self.plat.slug]), contenu)

    def test_toutes_les_actions_du_proprietaire_presentes(self):
        contenu = self.contenu()
        for libelle in [
            "Ajouter un test de cuisson",
            "Ajouter une recette",
            "Modifier le plat",
            "Supprimer le plat",
        ]:
            with self.subTest(libelle=libelle):
                self.assertIn(libelle, contenu)

    def test_page_de_recette_accessible(self):
        reponse = self.client.get(reverse("plats:modifier_recette", args=[self.plat.slug]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Ingrédients")
        self.assertContains(reponse, "Étapes de préparation")


class ParcoursCreationTest(TestCase):
    """Les deux usages doivent se choisir dès la création du plat."""

    def setUp(self):
        self.membre = creer_membre()
        self.client.force_login(self.membre)

    def donnees_plat(self, nom):
        return {"nom": nom, "description": "", "nombre_personnes": 4}

    def test_les_deux_boutons_sont_proposes(self):
        reponse = self.client.get(reverse("plats:creer"))
        self.assertContains(reponse, "Enregistrer")
        self.assertContains(reponse, "Enregistrer puis écrire la recette")

    def test_plat_simple_va_vers_la_fiche(self):
        """Cordons bleus surgelés : température et temps suffisent."""
        from plats.models import Plat

        reponse = self.client.post(reverse("plats:creer"), self.donnees_plat("Cordon bleu"))
        plat = Plat.objects.get(nom="Cordon bleu")
        self.assertRedirects(reponse, plat.get_absolute_url())

    def test_plat_avec_recette_va_vers_la_recette(self):
        """Poulet au curry : on enchaîne directement sur les ingrédients."""
        from plats.models import Plat

        donnees = self.donnees_plat("Poulet au curry")
        donnees["suite"] = "recette"
        reponse = self.client.post(reverse("plats:creer"), donnees)
        plat = Plat.objects.get(nom="Poulet au curry")
        self.assertRedirects(
            reponse, reverse("plats:modifier_recette", args=[plat.slug])
        )

    def test_le_plat_est_bien_cree_dans_les_deux_cas(self):
        from plats.models import Plat

        self.client.post(reverse("plats:creer"), self.donnees_plat("Cordon bleu"))
        donnees = self.donnees_plat("Poulet au curry")
        donnees["suite"] = "recette"
        self.client.post(reverse("plats:creer"), donnees)
        self.assertEqual(Plat.objects.filter(proprietaire=self.membre).count(), 2)

    def test_modification_peut_aussi_enchainer_sur_la_recette(self):
        plat = creer_plat(self.membre, nom="Poulet au curry")
        donnees = self.donnees_plat("Poulet au curry")
        donnees["suite"] = "recette"
        reponse = self.client.post(reverse("plats:modifier", args=[plat.slug]), donnees)
        self.assertRedirects(
            reponse, reverse("plats:modifier_recette", args=[plat.slug])
        )

    def test_assez_de_lignes_pour_une_vraie_recette(self):
        """Sans JavaScript, les lignes vides doivent être fournies d'avance."""
        plat = creer_plat(self.membre, nom="Poulet au curry")
        reponse = self.client.get(reverse("plats:modifier_recette", args=[plat.slug]))
        self.assertEqual(reponse.context["jeux"]["ingredients"].total_form_count(), 8)
        self.assertEqual(reponse.context["jeux"]["etapes"].total_form_count(), 5)

    def test_recette_complete_enregistree(self):
        """Le cas concret : poulet, huile d'olive, curry en poudre."""
        plat = creer_plat(self.membre, nom="Poulet au curry", nombre_personnes=4)
        donnees = {
            "ingredients-TOTAL_FORMS": "3",
            "ingredients-INITIAL_FORMS": "0",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-nom": "blanc de poulet",
            "ingredients-0-quantite": "600",
            "ingredients-0-unite": "g",
            "ingredients-1-nom": "huile d'olive",
            "ingredients-1-quantite": "1",
            "ingredients-1-unite": "cs",
            "ingredients-2-nom": "curry en poudre",
            "ingredients-2-quantite": "",
            "ingredients-2-unite": "",
            "etapes-TOTAL_FORMS": "1",
            "etapes-INITIAL_FORMS": "0",
            "etapes-MIN_NUM_FORMS": "0",
            "etapes-MAX_NUM_FORMS": "1000",
            "etapes-0-texte": "Enrober le poulet d'huile et de curry.",
        }
        self.client.post(reverse("plats:modifier_recette", args=[plat.slug]), donnees)

        libelles = [ingredient.libelle for ingredient in plat.ingredients.all()]
        self.assertEqual(
            libelles,
            [
                "600 g de blanc de poulet",
                "1 cuillère à soupe d'huile d'olive",
                "curry en poudre",
            ],
        )
        self.assertEqual(plat.etapes.count(), 1)


class ElisionTest(TestCase):
    """« de farine » mais « d'huile » : l'élision doit suivre le mot."""

    def setUp(self):
        self.plat = creer_plat(creer_membre())

    def libelle(self, nom, unite="g"):
        return creer_ingredient(self.plat, nom, "100", unite).libelle

    def test_consonne(self):
        self.assertEqual(self.libelle("farine"), "100 g de farine")

    def test_voyelle(self):
        self.assertEqual(self.libelle("origan"), "100 g d'origan")

    def test_h_muet(self):
        self.assertEqual(
            creer_ingredient(self.plat, "huile d'olive", "1", "cs").libelle,
            "1 cuillère à soupe d'huile d'olive",
        )

    def test_h_aspire(self):
        self.assertEqual(self.libelle("haricots verts"), "100 g de haricots verts")

    def test_voyelle_accentuee(self):
        self.assertEqual(self.libelle("échalotes"), "100 g d'échalotes")

    def test_majuscule(self):
        self.assertEqual(self.libelle("Emmental"), "100 g d'Emmental")

    def test_sans_unite_pas_de_preposition(self):
        self.assertEqual(
            creer_ingredient(self.plat, "œufs", "2", "").libelle, "2 œufs"
        )
