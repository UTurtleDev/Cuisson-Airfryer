from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

Utilisateur = get_user_model()


class ModeleUtilisateurTest(TestCase):
    def test_creation_avec_email_seulement(self):
        utilisateur = Utilisateur.objects.creer_utilisateur(
            email="marie@exemple.fr", mot_de_passe="MotDePasse123!"
        )
        self.assertEqual(utilisateur.email, "marie@exemple.fr")
        self.assertEqual(utilisateur.prenom, "")
        self.assertEqual(utilisateur.nom, "")
        self.assertTrue(utilisateur.is_active)
        self.assertFalse(utilisateur.is_staff)
        self.assertTrue(utilisateur.check_password("MotDePasse123!"))

    def test_email_obligatoire(self):
        with self.assertRaises(ValueError):
            Utilisateur.objects.creer_utilisateur(email="", mot_de_passe="MotDePasse123!")

    def test_email_unique(self):
        Utilisateur.objects.creer_utilisateur(email="paul@exemple.fr", mot_de_passe="MotDePasse123!")
        with self.assertRaises(IntegrityError):
            Utilisateur.objects.creer_utilisateur(
                email="paul@exemple.fr", mot_de_passe="AutreMotDePasse123!"
            )

    def test_superutilisateur(self):
        administrateur = Utilisateur.objects.creer_superutilisateur(
            email="admin@exemple.fr", mot_de_passe="MotDePasse123!"
        )
        self.assertTrue(administrateur.is_staff)
        self.assertTrue(administrateur.is_superuser)

    def test_nom_affiche(self):
        utilisateur = Utilisateur.objects.creer_utilisateur(
            email="lea@exemple.fr", mot_de_passe="MotDePasse123!", prenom="Léa", nom="Martin"
        )
        self.assertEqual(utilisateur.nom_complet, "Léa Martin")
        self.assertEqual(str(utilisateur), "Léa Martin")

    def test_nom_affiche_replie_sur_email(self):
        utilisateur = Utilisateur.objects.creer_utilisateur(
            email="anonyme@exemple.fr", mot_de_passe="MotDePasse123!"
        )
        self.assertEqual(utilisateur.nom_affiche, "anonyme@exemple.fr")
