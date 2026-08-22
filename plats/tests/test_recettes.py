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
        self.assertEqual(ingredient.libelle, "2 cuillère à soupe de huile")


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
        self.assertContains(reponse, "Aucune recette pour ce plat")

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
