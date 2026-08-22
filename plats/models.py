from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from plats.managers import PlatQuerySet


class Categorie(models.Model):
    """Catégorie de plat, gérable depuis l'administration.

    La liste initiale est posée par une migration de données ; elle peut
    ensuite évoluer sans toucher au code.
    """

    nom = models.CharField("nom", max_length=60, unique=True)
    slug = models.SlugField("identifiant d'URL", max_length=60, unique=True)
    est_active = models.BooleanField(
        "active",
        default=True,
        help_text="Décocher pour masquer la catégorie sans supprimer les liens existants.",
    )
    ordre = models.PositiveSmallIntegerField("ordre d'affichage", default=0)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class Plat(models.Model):
    """Plat testé par un membre de la famille.

    Le plat porte aussi les informations de recette (nombre de personnes,
    temps de préparation) afin que les ingrédients et les étapes puissent lui
    être rattachés plus tard sans restructuration.
    """

    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="propriétaire",
        on_delete=models.CASCADE,
        related_name="plats",
    )
    nom = models.CharField("nom", max_length=120)
    slug = models.SlugField("identifiant d'URL", max_length=140, unique=True, blank=True)
    description = models.TextField("description", blank=True)
    image = models.ImageField("image", upload_to="plats/%Y/%m", blank=True)
    categories = models.ManyToManyField(
        Categorie,
        verbose_name="catégories",
        related_name="plats",
        blank=True,
    )

    nombre_personnes = models.PositiveSmallIntegerField("nombre de personnes", default=4)
    temps_preparation_minutes = models.PositiveSmallIntegerField(
        "temps de préparation (minutes)", null=True, blank=True
    )

    plat_origine = models.ForeignKey(
        "self",
        verbose_name="plat d'origine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copies",
        help_text="Renseigné lorsque ce plat est la copie du plat d'un autre membre.",
    )

    date_creation = models.DateTimeField("date de création", auto_now_add=True)
    date_modification = models.DateTimeField("date de modification", auto_now=True)

    objects = PlatQuerySet.as_manager()

    class Meta:
        verbose_name = "plat"
        verbose_name_plural = "plats"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["-date_creation"]),
        ]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.slug_disponible()
        super().save(*args, **kwargs)

    def slug_disponible(self):
        """Construit un slug unique à partir du nom, avec suffixe si besoin."""
        base = slugify(self.nom)[:130] or "plat"
        candidat = base
        compteur = 2
        while Plat.objects.filter(slug=candidat).exclude(pk=self.pk).exists():
            candidat = f"{base}-{compteur}"
            compteur += 1
        return candidat

    def get_absolute_url(self):
        return reverse("plats:detail", kwargs={"slug": self.slug})

    def appartient_a(self, utilisateur):
        return utilisateur.is_authenticated and self.proprietaire_id == utilisateur.pk
