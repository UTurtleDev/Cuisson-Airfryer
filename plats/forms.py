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
