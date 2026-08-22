from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from plats.models import Plat, TestCuisson

NOMBRE_MIS_EN_AVANT = 6


class AccueilView(TemplateView):
    """Page d'accueil.

    Les plats ne sont mis en avant que pour les membres connectés : le carnet
    est familial, rien n'est exposé aux visiteurs de passage.

    La notion de « meilleurs plats » est volontairement composée de plusieurs
    listes courtes, chacune pouvant évoluer indépendamment.
    """

    template_name = "principal/accueil.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            return contexte

        plats = Plat.objects.visibles().avec_details()
        contexte["plats_avec_meilleure_combinaison"] = plats.avec_meilleur_test().recents()[
            :NOMBRE_MIS_EN_AVANT
        ]
        contexte["plats_mieux_notes"] = plats.mieux_notes()[:NOMBRE_MIS_EN_AVANT]
        contexte["plats_recents"] = plats.recents()[:NOMBRE_MIS_EN_AVANT]
        return contexte


class TableauDeBordView(LoginRequiredMixin, TemplateView):
    """Point d'entrée de l'utilisateur connecté."""

    template_name = "principal/tableau_de_bord.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        mes_plats = Plat.objects.de(self.request.user).avec_details()
        contexte["mes_plats"] = mes_plats.recents()[:NOMBRE_MIS_EN_AVANT]
        contexte["nombre_de_plats"] = mes_plats.count()
        contexte["derniers_tests"] = (
            TestCuisson.objects.filter(plat__proprietaire=self.request.user)
            .select_related("plat")
            .order_by("-date_test", "-id")[:5]
        )
        return contexte
