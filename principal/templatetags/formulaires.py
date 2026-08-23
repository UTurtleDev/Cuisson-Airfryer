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


@register.simple_tag(takes_context=True)
def champ_exclu(context, champ):
    """Vrai si le champ figure dans la variable de contexte `champs_exclus`.

    Balise plutôt que filtre : une variable de contexte absente passée en
    argument de filtre fait échouer toute la condition qui l'entoure, et
    le formulaire se rend alors vide, sans la moindre erreur.

    On compare des noms entiers : sans cela, exclure « note » écarterait
    aussi « notes » par simple sous-chaîne.
    """
    noms = context.get("champs_exclus") or ""
    return champ.name in [nom.strip() for nom in str(noms).split(",")]

