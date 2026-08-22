from django.test import TestCase
from django.urls import reverse

from plats.models import Favori, Plat
from plats.services import basculer_favori
from plats.tests.fabriques import creer_membre, creer_plat


class ServiceFavoriTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.autre)

    def test_ajout(self):
        self.assertTrue(basculer_favori(self.plat, self.membre))
        self.assertEqual(Favori.objects.count(), 1)

    def test_retrait(self):
        basculer_favori(self.plat, self.membre)
        self.assertFalse(basculer_favori(self.plat, self.membre))
        self.assertEqual(Favori.objects.count(), 0)

    def test_le_plat_n_est_pas_modifie(self):
        date_avant = self.plat.date_modification
        basculer_favori(self.plat, self.membre)
        self.plat.refresh_from_db()
        self.assertEqual(self.plat.date_modification, date_avant)
        self.assertEqual(self.plat.proprietaire, self.autre)

    def test_plusieurs_membres_sur_le_meme_plat(self):
        troisieme = creer_membre("troisieme@exemple.fr")
        basculer_favori(self.plat, self.membre)
        basculer_favori(self.plat, troisieme)
        self.assertEqual(self.plat.favoris.count(), 2)

    def test_retrait_ne_supprime_pas_le_plat(self):
        basculer_favori(self.plat, self.membre)
        basculer_favori(self.plat, self.membre)
        self.assertTrue(Plat.objects.filter(pk=self.plat.pk).exists())

    def test_un_seul_favori_par_membre_et_plat(self):
        from django.db import IntegrityError

        basculer_favori(self.plat, self.membre)
        with self.assertRaises(IntegrityError):
            Favori.objects.create(utilisateur=self.membre, plat=self.plat)


class VueFavoriTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.plat = creer_plat(self.autre, nom="Onion rings")
        self.url = reverse("plats:basculer_favori", args=[self.plat.slug])
        self.client.force_login(self.membre)

    def test_connexion_requise(self):
        self.client.logout()
        reponse = self.client.post(self.url)
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Favori.objects.count(), 0)

    def test_ajout_puis_retrait(self):
        self.client.post(self.url)
        self.assertEqual(Favori.objects.count(), 1)
        self.client.post(self.url)
        self.assertEqual(Favori.objects.count(), 0)

    def test_methode_get_refusee(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_reponse_htmx_limitee_au_bouton(self):
        reponse = self.client.post(self.url, headers={"HX-Request": "true"})
        self.assertContains(reponse, "En favori")
        self.assertContains(reponse, 'aria-pressed="true"')
        self.assertNotContains(reponse, "<!DOCTYPE html>")

    def test_le_bouton_htmx_repasse_a_l_etat_initial(self):
        self.client.post(self.url, headers={"HX-Request": "true"})
        reponse = self.client.post(self.url, headers={"HX-Request": "true"})
        self.assertContains(reponse, "Ajouter aux favoris")
        self.assertContains(reponse, 'aria-pressed="false"')

    def test_favori_sur_son_propre_plat_autorise(self):
        mien = creer_plat(self.membre, nom="Hamburger")
        self.client.post(reverse("plats:basculer_favori", args=[mien.slug]))
        self.assertEqual(Favori.objects.count(), 1)


class ListeFavorisTest(TestCase):
    def setUp(self):
        self.membre = creer_membre()
        self.autre = creer_membre("autre@exemple.fr")
        self.garde = creer_plat(self.autre, nom="Onion rings")
        self.ignore = creer_plat(self.autre, nom="Gnocchi")
        basculer_favori(self.garde, self.membre)
        self.client.force_login(self.membre)

    def test_ne_liste_que_mes_favoris(self):
        reponse = self.client.get(reverse("plats:favoris"))
        self.assertEqual(list(reponse.context["plats"]), [self.garde])

    def test_favoris_des_autres_invisibles(self):
        basculer_favori(self.ignore, self.autre)
        reponse = self.client.get(reverse("plats:favoris"))
        self.assertEqual(list(reponse.context["plats"]), [self.garde])

    def test_liste_vide(self):
        Favori.objects.all().delete()
        reponse = self.client.get(reverse("plats:favoris"))
        self.assertContains(reponse, "Aucun favori")

    def test_filtre_favoris_dans_la_liste_des_plats(self):
        reponse = self.client.get(reverse("plats:liste"), {"favoris_uniquement": "on"})
        self.assertEqual(list(reponse.context["plats"]), [self.garde])

    def test_annotation_sans_requete_par_plat(self):
        """L'état favori est annoté : le coût ne croît pas avec la liste.

        Le nombre exact de requêtes importe peu, ce qui compte est qu'il
        reste identique quand la liste s'allonge.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        def requetes_pour_la_liste():
            with CaptureQueriesContext(connection) as capture:
                reponse = self.client.get(reverse("plats:liste"))
                list(reponse.context["plats"])
            return len(capture)

        cout_initial = requetes_pour_la_liste()
        for numero in range(8):
            creer_plat(self.autre, nom=f"Plat supplémentaire {numero}")
        self.assertEqual(requetes_pour_la_liste(), cout_initial)
