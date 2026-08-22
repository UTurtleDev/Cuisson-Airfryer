from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class AccueilView(TemplateView):
    """Page d'accueil publique.

    Elle mettra en avant les meilleurs plats une fois l'application plats
    en place (lot 4).
    """

    template_name = "principal/accueil.html"


class TableauDeBordView(LoginRequiredMixin, TemplateView):
    """Point d'entrée de l'utilisateur connecté."""

    template_name = "principal/tableau_de_bord.html"
