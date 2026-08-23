"""Filtres d'aide au rendu des formulaires."""

from django import forms
from django.template import Library

register = Library()


@register.filter
def est_case_a_cocher(champ):
    """Vrai pour une case unique, qui demande le markup `.radio` + `.dot`."""
    return isinstance(champ.field.widget, forms.CheckboxInput)


@register.filter
def est_groupe_de_cases(champ):
    """Vrai pour un groupe de cases, rendu en série de `.radio`."""
    return isinstance(champ.field.widget, forms.CheckboxSelectMultiple)


@register.filter
def est_groupe_radio(champ):
    """Vrai pour un groupe de boutons radio, rendu en segmenté `.seg`."""
    return isinstance(champ.field.widget, forms.RadioSelect)


@register.filter
def est_exclu(champ, noms):
    """Vrai si le champ figure dans la liste de noms séparés par des virgules.

    On compare des noms entiers : sans cela, exclure « note » écarterait
    aussi « notes » par simple sous-chaîne.
    """
    if not noms:
        return False
    return champ.name in [nom.strip() for nom in noms.split(",")]
