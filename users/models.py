from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from users.managers import GestionnaireUtilisateur


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Compte d'un membre de la famille.

    L'authentification se fait avec l'adresse électronique ; le nom et le
    prénom restent facultatifs.

    Les champs ``is_active``, ``is_staff`` et ``is_superuser`` gardent leur nom
    anglais car Django et son administration s'appuient dessus. Leur libellé
    affiché est en français.
    """

    email = models.EmailField("adresse électronique", unique=True)
    prenom = models.CharField("prénom", max_length=150, blank=True)
    nom = models.CharField("nom", max_length=150, blank=True)

    is_active = models.BooleanField(
        "compte actif",
        default=True,
        help_text="Décocher pour désactiver un compte sans le supprimer.",
    )
    is_staff = models.BooleanField(
        "accès à l'administration",
        default=False,
        help_text="Réservé aux administrateurs du site.",
    )
    date_inscription = models.DateTimeField("date d'inscription", default=timezone.now)

    objects = GestionnaireUtilisateur()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["email"]

    def __str__(self):
        return self.nom_affiche

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def nom_affiche(self):
        """Nom à afficher dans l'interface, avec repli sur l'adresse."""
        return self.nom_complet or self.prenom or self.email

    # Compatibilité avec l'administration Django.
    def get_full_name(self):
        return self.nom_complet

    def get_short_name(self):
        return self.prenom or self.email
