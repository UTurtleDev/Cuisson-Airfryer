from django.contrib.auth.models import BaseUserManager


class GestionnaireUtilisateur(BaseUserManager):
    """Gestionnaire du modèle Utilisateur, basé sur l'adresse électronique.

    Les méthodes ``create_user`` et ``create_superuser`` conservent leur nom
    anglais : Django les appelle directement, notamment la commande
    ``createsuperuser``. Des alias en français sont fournis pour le code du
    projet.
    """

    use_in_migrations = True

    def create_user(self, email, password=None, **champs_supplementaires):
        if not email:
            raise ValueError("Une adresse électronique est obligatoire.")

        champs_supplementaires.setdefault("is_active", True)
        utilisateur = self.model(email=self.normalize_email(email), **champs_supplementaires)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, email, password=None, **champs_supplementaires):
        champs_supplementaires.setdefault("is_staff", True)
        champs_supplementaires.setdefault("is_superuser", True)

        if champs_supplementaires.get("is_staff") is not True:
            raise ValueError("Un superutilisateur doit avoir is_staff=True.")
        if champs_supplementaires.get("is_superuser") is not True:
            raise ValueError("Un superutilisateur doit avoir is_superuser=True.")

        return self.create_user(email, password, **champs_supplementaires)

    # Alias en français, à privilégier dans le code du projet.
    def creer_utilisateur(self, email, mot_de_passe=None, **champs_supplementaires):
        return self.create_user(email, mot_de_passe, **champs_supplementaires)

    def creer_superutilisateur(self, email, mot_de_passe=None, **champs_supplementaires):
        return self.create_superuser(email, mot_de_passe, **champs_supplementaires)
