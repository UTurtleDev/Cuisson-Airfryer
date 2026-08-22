from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

Utilisateur = get_user_model()


class InscriptionTest(TestCase):
    def test_inscription_cree_le_compte_et_connecte(self):
        reponse = self.client.post(
            reverse("users:inscription"),
            {
                "email": "nouveau@exemple.fr",
                "prenom": "Sacha",
                "nom": "",
                "password1": "MotDePasseSolide123",
                "password2": "MotDePasseSolide123",
            },
        )
        self.assertRedirects(reponse, reverse("principal:tableau_de_bord"))
        self.assertTrue(Utilisateur.objects.filter(email="nouveau@exemple.fr").exists())
        self.assertIn("_auth_user_id", self.client.session)


class ConnexionTest(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.creer_utilisateur(
            email="membre@exemple.fr", mot_de_passe="MotDePasseSolide123"
        )

    def test_connexion_par_email(self):
        reponse = self.client.post(
            reverse("users:connexion"),
            {"username": "membre@exemple.fr", "password": "MotDePasseSolide123"},
        )
        self.assertRedirects(reponse, reverse("principal:tableau_de_bord"))

    def test_connexion_refusee_si_mot_de_passe_incorrect(self):
        reponse = self.client.post(
            reverse("users:connexion"),
            {"username": "membre@exemple.fr", "password": "mauvais"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_connexion_refusee_si_compte_desactive(self):
        self.utilisateur.is_active = False
        self.utilisateur.save()
        self.client.post(
            reverse("users:connexion"),
            {"username": "membre@exemple.fr", "password": "MotDePasseSolide123"},
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deconnexion(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(reverse("users:deconnexion"))
        self.assertRedirects(reponse, reverse("principal:accueil"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfilTest(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.creer_utilisateur(
            email="profil@exemple.fr", mot_de_passe="MotDePasseSolide123"
        )

    def test_profil_inaccessible_sans_connexion(self):
        reponse = self.client.get(reverse("users:profil"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("users:connexion"), reponse.url)

    def test_modification_du_profil(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(
            reverse("users:profil"),
            {"email": "profil@exemple.fr", "prenom": "Camille", "nom": "Durand"},
        )
        self.assertRedirects(reponse, reverse("users:profil"))
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.prenom, "Camille")


class AccesAdministrationTest(TestCase):
    def test_utilisateur_classique_refuse(self):
        utilisateur = Utilisateur.objects.creer_utilisateur(
            email="simple@exemple.fr", mot_de_passe="MotDePasseSolide123"
        )
        self.client.force_login(utilisateur)
        reponse = self.client.get("/admin/")
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("login", reponse.url)

    def test_administrateur_autorise(self):
        administrateur = Utilisateur.objects.creer_superutilisateur(
            email="chef@exemple.fr", mot_de_passe="MotDePasseSolide123"
        )
        self.client.force_login(administrateur)
        reponse = self.client.get("/admin/")
        self.assertEqual(reponse.status_code, 200)


class ReinitialisationMotDePasseTest(TestCase):
    def test_demande_envoie_un_courriel(self):
        Utilisateur.objects.creer_utilisateur(
            email="oubli@exemple.fr", mot_de_passe="MotDePasseSolide123"
        )
        reponse = self.client.post(
            reverse("users:reinitialisation"), {"email": "oubli@exemple.fr"}
        )
        self.assertRedirects(reponse, reverse("users:reinitialisation_envoyee"))
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("mot-de-passe/reinitialiser/", mail.outbox[0].body)
