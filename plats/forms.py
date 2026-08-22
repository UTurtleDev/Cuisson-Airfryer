from django import forms

from plats.models import Categorie, Plat


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
