from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from plats.images import LARGEUR_MINIMUM
from plats.managers import PlatQuerySet
from plats.validateurs import (
    TAILLE_MAXIMUM_MEGAOCTETS,
    valider_taille_image,
)


#: Mots commençant par un h aspiré, devant lequel « de » ne s'élide pas.
H_ASPIRE = ("haricot", "hareng", "homard", "hachis", "houmous", "hot-dog")


def elider(nom):
    """Renvoie « de farine » ou « d'huile », selon l'initiale du mot.

    Le h aspiré fait exception : on dit « de haricots », pas « d'haricots ».
    """
    premier_mot = nom.lstrip().lower()
    if premier_mot.startswith(H_ASPIRE):
        return f"de {nom}"
    if premier_mot[:1] in "aeiouyâàéèêëîïôöûùh":
        return f"d'{nom}"
    return f"de {nom}"


def format_nombre(quantite):
    """Affiche une quantité sans décimales inutiles : 250, 2.5, 0.75."""
    quantite = quantite.normalize()
    if quantite == quantite.to_integral_value():
        quantite = quantite.quantize(Decimal(1))
    return f"{quantite:f}".replace(".", ",")


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
    image = models.ImageField(
        "image",
        upload_to="plats/%Y/%m",
        blank=True,
        validators=[valider_taille_image],
        help_text=(
            "Facultative. Elle est recadrée et allégée automatiquement, inutile "
            f"de la préparer : au moins {LARGEUR_MINIMUM} pixels de large, "
            f"{TAILLE_MAXIMUM_MEGAOCTETS} Mo maximum."
        ),
    )
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

    @property
    def a_une_recette(self):
        return self.ingredients.exists() or self.etapes.exists()

    def tests_numerotes(self):
        """Tests du plus récent au plus ancien, numérotés dans l'ordre des essais.

        Le premier essai réalisé porte le numéro 1, quel que soit l'ordre
        d'affichage : c'est le repère naturel quand on compare des essais.
        """
        tests = list(self.tests.all())
        total = len(tests)
        for rang, test in enumerate(tests):
            # On pose le rang calculé en une passe plutôt que de laisser
            # chaque essai l'interroger de son côté.
            test.__dict__["numero"] = total - rang

        # La meilleure combinaison remonte en tête de liste, mais garde son
        # numéro : le numéro dit quand l'essai a été fait, pas son rang.
        # Le tri est stable, les autres essais conservent leur ordre.
        tests.sort(key=lambda test: test.pk != self.meilleur_test_id)
        return tests

    @property
    def numero_du_test_retenu(self):
        """Numéro d'essai de la combinaison retenue, pour l'affichage."""
        if not self.meilleur_test_id:
            return None
        for test in self.tests_numerotes():
            if test.pk == self.meilleur_test_id:
                return test.numero
        return None

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
        """Note de 1 à 5.

        Les libellés sont les chiffres eux-mêmes : c'est ce qu'affiche le
        contrôle segmenté du design system. Les étoiles sont un rendu, pas
        une valeur, et vivent dans le fragment `partiels/note.html`.
        """

        UNE = 1, "1"
        DEUX = 2, "2"
        TROIS = 3, "3"
        QUATRE = 4, "4"
        CINQ = 5, "5"

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
    def numero(self):
        """Rang chronologique de cet essai parmi ceux du plat.

        Défini comme attribut par `Plat.tests_numerotes()` pour les listes ;
        cette propriété sert quand on manipule un essai isolé.
        """
        anterieurs = TestCuisson.objects.filter(plat_id=self.plat_id).filter(
            models.Q(date_test__lt=self.date_test)
            | models.Q(date_test=self.date_test, id__lte=self.pk)
        )
        return anterieurs.count()

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


class Favori(models.Model):
    """Plat mis de côté par un membre.

    Un favori est personnel et n'a aucun effet sur le plat : il ne le copie
    pas, ne le modifie pas, et plusieurs membres peuvent mettre le même plat
    dans leurs favoris.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="membre",
        on_delete=models.CASCADE,
        related_name="favoris",
    )
    plat = models.ForeignKey(
        Plat,
        verbose_name="plat",
        on_delete=models.CASCADE,
        related_name="favoris",
    )
    date_ajout = models.DateTimeField("date d'ajout", auto_now_add=True)

    class Meta:
        verbose_name = "favori"
        verbose_name_plural = "favoris"
        ordering = ["-date_ajout"]
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "plat"],
                name="favori_unique_par_membre_et_plat",
            )
        ]

    def __str__(self):
        return f"{self.utilisateur} ♥ {self.plat}"


class Ingredient(models.Model):
    """Ingrédient d'un plat, avec sa quantité pour le nombre de personnes du plat."""

    class Unite(models.TextChoices):
        GRAMME = "g", "g"
        KILOGRAMME = "kg", "kg"
        MILLILITRE = "ml", "ml"
        CENTILITRE = "cl", "cl"
        LITRE = "l", "l"
        CUILLERE_CAFE = "cc", "cuillère à café"
        CUILLERE_SOUPE = "cs", "cuillère à soupe"
        PINCEE = "pincee", "pincée"
        TRANCHE = "tranche", "tranche"

    plat = models.ForeignKey(
        Plat,
        verbose_name="plat",
        on_delete=models.CASCADE,
        related_name="ingredients",
    )
    nom = models.CharField("ingrédient", max_length=120)
    quantite = models.DecimalField(
        "quantité",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Laisser vide pour une quantité libre (« sel », « poivre »).",
    )
    unite = models.CharField(
        "unité",
        max_length=10,
        choices=Unite.choices,
        blank=True,
        help_text="Vide pour compter en pièces (« 2 œufs »).",
    )
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "ingrédient"
        verbose_name_plural = "ingrédients"
        ordering = ["ordre", "id"]

    def __str__(self):
        return self.libelle

    @property
    def libelle(self):
        """Texte affichable : « 250 g de farine », « 2 œufs », « sel »."""
        return self.libelle_pour(self.quantite)

    def libelle_pour(self, quantite):
        if quantite is None:
            return self.nom
        nombre = format_nombre(quantite)
        if self.unite:
            return f"{nombre} {self.get_unite_display()} {elider(self.nom)}"
        return f"{nombre} {self.nom}"


class EtapePreparation(models.Model):
    """Étape de préparation d'un plat."""

    plat = models.ForeignKey(
        Plat,
        verbose_name="plat",
        on_delete=models.CASCADE,
        related_name="etapes",
    )
    ordre = models.PositiveSmallIntegerField("ordre", default=0)
    texte = models.TextField("étape")

    class Meta:
        verbose_name = "étape de préparation"
        verbose_name_plural = "étapes de préparation"
        ordering = ["ordre", "id"]

    def __str__(self):
        return f"Étape {self.ordre}"
