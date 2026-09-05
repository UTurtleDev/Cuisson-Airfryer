from django.contrib import admin

from plats.forms import FormulairePlatAdministration
from plats.models import (
    Categorie,
    EtapePreparation,
    Favori,
    Ingredient,
    Plat,
    TestCuisson,
)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ["nom", "ordre", "est_active", "nombre_de_plats"]
    list_editable = ["ordre", "est_active"]
    list_filter = ["est_active"]
    search_fields = ["nom"]
    prepopulated_fields = {"slug": ["nom"]}

    @admin.display(description="plats")
    def nombre_de_plats(self, categorie):
        return categorie.plats.count()


class IngredientEnLigne(admin.TabularInline):
    model = Ingredient
    extra = 0
    fields = ["ordre", "nom", "quantite", "unite"]
    ordering = ["ordre", "id"]


class EtapeEnLigne(admin.TabularInline):
    model = EtapePreparation
    extra = 0
    fields = ["ordre", "texte"]
    ordering = ["ordre", "id"]


class TestCuissonEnLigne(admin.TabularInline):
    """Tests de cuisson consultables directement depuis la fiche du plat."""

    model = TestCuisson
    extra = 0
    fields = ["date_test", "temperature_celsius", "duree_minutes", "note", "commentaire"]
    ordering = ["-date_test"]


@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    form = FormulairePlatAdministration
    list_display = ["nom", "proprietaire", "meilleur_test", "date_creation", "est_une_copie"]
    list_filter = ["categories", "date_creation"]
    search_fields = ["nom", "description", "proprietaire__email"]
    autocomplete_fields = ["proprietaire", "plat_origine", "meilleur_test"]
    inlines = [IngredientEnLigne, EtapeEnLigne, TestCuissonEnLigne]
    filter_horizontal = ["categories"]
    readonly_fields = ["date_creation", "date_modification"]
    date_hierarchy = "date_creation"

    fieldsets = [
        (None, {"fields": ["proprietaire", "nom", "slug", "description", "image"]}),
        ("Classement", {"fields": ["categories"]}),
        ("Recette", {"fields": ["nombre_personnes", "temps_preparation_minutes"]}),
        ("Cuisson", {"fields": ["meilleur_test"]}),
        ("Origine", {"fields": ["plat_origine"]}),
        ("Dates", {"fields": ["date_creation", "date_modification"]}),
    ]

    @admin.display(description="copie", boolean=True)
    def est_une_copie(self, plat):
        return plat.plat_origine_id is not None

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("proprietaire")


@admin.register(TestCuisson)
class TestCuissonAdmin(admin.ModelAdmin):
    list_display = [
        "plat",
        "date_test",
        "temperature_celsius",
        "duree_minutes",
        "note",
        "est_meilleur",
    ]
    list_filter = ["note", "date_test"]
    search_fields = ["plat__nom", "commentaire", "plat__proprietaire__email"]
    autocomplete_fields = ["plat"]
    date_hierarchy = "date_test"
    readonly_fields = ["date_creation"]

    @admin.display(description="meilleure combinaison", boolean=True)
    def est_meilleur(self, test):
        return test.est_meilleur

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("plat", "plat__proprietaire")


@admin.register(Favori)
class FavoriAdmin(admin.ModelAdmin):
    list_display = ["utilisateur", "plat", "date_ajout"]
    list_filter = ["date_ajout"]
    search_fields = ["utilisateur__email", "plat__nom"]
    autocomplete_fields = ["utilisateur", "plat"]
    readonly_fields = ["date_ajout"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("utilisateur", "plat")
