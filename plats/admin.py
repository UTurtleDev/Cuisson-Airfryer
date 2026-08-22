from django.contrib import admin

from plats.models import Categorie, Plat


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


@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    list_display = ["nom", "proprietaire", "date_creation", "est_une_copie"]
    list_filter = ["categories", "date_creation"]
    search_fields = ["nom", "description", "proprietaire__email"]
    autocomplete_fields = ["proprietaire", "plat_origine"]
    filter_horizontal = ["categories"]
    readonly_fields = ["date_creation", "date_modification"]
    date_hierarchy = "date_creation"

    fieldsets = [
        (None, {"fields": ["proprietaire", "nom", "slug", "description", "image"]}),
        ("Classement", {"fields": ["categories"]}),
        ("Recette", {"fields": ["nombre_personnes", "temps_preparation_minutes"]}),
        ("Origine", {"fields": ["plat_origine"]}),
        ("Dates", {"fields": ["date_creation", "date_modification"]}),
    ]

    @admin.display(description="copie", boolean=True)
    def est_une_copie(self, plat):
        return plat.plat_origine_id is not None

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("proprietaire")
