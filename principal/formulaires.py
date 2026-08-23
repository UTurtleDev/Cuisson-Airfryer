"""Habillage des formulaires par le design system.

Le système impose ses classes sur les contrôles : `.input` sur les champs de
saisie, `.radio` + `.dot` sur les cases, `.seg` sur les groupes de boutons.
Plutôt que de les répéter dans chaque formulaire, ce mixin les pose
automatiquement selon le type de widget.
"""

from django import forms
from django.forms.widgets import Input

CLASSES_PAR_WIDGET = (
    (forms.CheckboxSelectMultiple, None),
    (forms.CheckboxInput, None),
    (forms.RadioSelect, None),
    (forms.Textarea, "input"),
    (forms.Select, "input"),
    (forms.SelectMultiple, "input"),
    (Input, "input"),
)


class HabillageNocturneMixin:
    """Ajoute les classes du design system aux widgets du formulaire."""

    def __init__(self, *args, **kwargs):
        # Le design system ecrit ses libelles sans deux-points.
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            classe = self.classe_du_widget(champ.widget)
            if not classe:
                continue
            existantes = champ.widget.attrs.get("class", "")
            champ.widget.attrs["class"] = f"{existantes} {classe}".strip()

    @staticmethod
    def classe_du_widget(widget):
        for type_widget, classe in CLASSES_PAR_WIDGET:
            if isinstance(widget, type_widget):
                return classe
        return None
