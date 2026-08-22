from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
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

    meilleur_test = models.ForeignKey(
        "TestCuisson",
        verbose_name="meilleure combinaison",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Test choisi manuellement comme meilleure cuisson de ce plat.",
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

    def tests_numerotes(self):
        """Tests du plus récent au plus ancien, numérotés dans l'ordre des essais.

        Le premier essai réalisé porte le numéro 1, quel que soit l'ordre
        d'affichage : c'est le repère naturel quand on compare des essais.
        """
        tests = list(self.tests.all())
        total = len(tests)
        for rang, test in enumerate(tests):
            test.numero = total - rang

        # La meilleure combinaison remonte en tête de liste, mais garde son
        # numéro : le numéro dit quand l'essai a été fait, pas son rang.
        # Le tri est stable, les autres essais conservent leur ordre.
        tests.sort(key=lambda test: test.pk != self.meilleur_test_id)
        return tests

    def definir_meilleur_test(self, test):
        """Désigne manuellement la meilleure combinaison de cuisson.

        Le test doit appartenir à ce plat. Un plat ne pointe qu'un seul
        meilleur test : l'unicité est structurelle, aucun test n'a de drapeau
        à maintenir de son côté.
        """
        if test is not None and test.plat_id != self.pk:
            raise ValueError("Ce test de cuisson n'appartient pas à ce plat.")
        self.meilleur_test = test
        self.save(update_fields=["meilleur_test", "date_modification"])


class TestCuisson(models.Model):
    """Essai de cuisson d'un plat.

    Chaque essai est conservé : un nouveau test ne remplace jamais un ancien,
    l'historique est le cœur de l'application.
    """

    class Note(models.IntegerChoices):
        UNE = 1, "★☆☆☆☆"
        DEUX = 2, "★★☆☆☆"
        TROIS = 3, "★★★☆☆"
        QUATRE = 4, "★★★★☆"
        CINQ = 5, "★★★★★"

    plat = models.ForeignKey(
        Plat,
        verbose_name="plat",
        on_delete=models.CASCADE,
        related_name="tests",
    )
    temperature_celsius = models.PositiveSmallIntegerField(
        "température (°C)",
        validators=[MinValueValidator(40), MaxValueValidator(260)],
    )
    duree_minutes = models.PositiveSmallIntegerField(
        "durée (minutes)",
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        help_text="Toujours en minutes, même au-delà d'une heure.",
    )
    note = models.PositiveSmallIntegerField("note", choices=Note.choices)
    commentaire = models.TextField("commentaire", blank=True)
    date_test = models.DateField("date du test", default=timezone.localdate)
    date_creation = models.DateTimeField("date d'enregistrement", auto_now_add=True)

    class Meta:
        verbose_name = "test de cuisson"
        verbose_name_plural = "tests de cuisson"
        ordering = ["-date_test", "-id"]
        indexes = [models.Index(fields=["plat", "-date_test"])]

    def __str__(self):
        return f"{self.temperature_celsius} °C / {self.duree_minutes} min"

    @property
    def est_meilleur(self):
        """Vrai si ce test est la meilleure combinaison retenue pour le plat."""
        return self.plat.meilleur_test_id == self.pk

    @property
    def duree_lisible(self):
        """Durée en heures et minutes, pour l'affichage seulement."""
        heures, minutes = divmod(self.duree_minutes, 60)
        if not heures:
            return f"{minutes} min"
        if not minutes:
            return f"{heures} h"
        return f"{heures} h {minutes:02d}"

    def get_absolute_url(self):
        return self.plat.get_absolute_url()
