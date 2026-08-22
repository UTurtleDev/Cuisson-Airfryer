from django import forms

from plats.models import Categorie, Plat, TestCuisson


class FormulairePlat(forms.ModelForm):
    """Création et modification d'un plat."""

    categories = forms.ModelMultipleChoiceField(
        label="catégories",
        queryset=Categorie.objects.filter(est_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Plat
        fields = [
            "nom",
            "description",
            "image",
            "categories",
            "nombre_personnes",
            "temps_preparation_minutes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "image": "Facultative.",
            "temps_preparation_minutes": "Facultatif, en minutes.",
        }


class FormulaireTestCuisson(forms.ModelForm):
    """Enregistrement d'un essai de cuisson."""

    class Meta:
        model = TestCuisson
        fields = ["temperature_celsius", "duree_minutes", "note", "commentaire", "date_test"]
        widgets = {
            "commentaire": forms.Textarea(attrs={"rows": 3}),
            "date_test": forms.DateInput(attrs={"type": "date"}),
            "temperature_celsius": forms.NumberInput(attrs={"min": 40, "max": 260, "step": 5}),
            "duree_minutes": forms.NumberInput(attrs={"min": 1, "max": 600}),
        }
        help_texts = {
            "commentaire": "Trop cuit, pas assez doré, parfait…",
        }


class FormulaireFiltrePlats(forms.Form):
    """Recherche et filtres de la liste des plats.

    Le formulaire porte lui-même la logique de filtrage : la vue reste courte
    et les filtres se combinent naturellement, chaque méthode du queryset
    renvoyant le queryset inchangé quand son critère est vide.
    """

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Hamburger, gnocchi…", "autocomplete": "off"}
        ),
    )
    categories = forms.ModelMultipleChoiceField(
        label="Catégories",
        queryset=Categorie.objects.filter(est_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    duree_maximum = forms.IntegerField(
        label="Cuisson maximum (minutes)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "20"}),
    )
    preparation_maximum = forms.IntegerField(
        label="Préparation maximum (minutes)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "15"}),
    )
    mes_plats_uniquement = forms.BooleanField(label="Seulement mes plats", required=False)
    avec_meilleure_combinaison = forms.BooleanField(
        label="Avec une meilleure combinaison", required=False
    )

    def filtrer(self, queryset, utilisateur):
        """Applique les critères renseignés, dans l'ordre, sur le queryset."""
        donnees = self.cleaned_data

        queryset = queryset.recherche(donnees.get("q"))
        queryset = queryset.par_categories(donnees.get("categories"))
        queryset = queryset.duree_cuisson_maximum(donnees.get("duree_maximum"))
        queryset = queryset.preparation_maximum(donnees.get("preparation_maximum"))

        if donnees.get("mes_plats_uniquement"):
            queryset = queryset.de(utilisateur)
        if donnees.get("avec_meilleure_combinaison"):
            queryset = queryset.avec_meilleur_test()

        return queryset
