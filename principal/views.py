from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.views.generic import TemplateView

from plats.models import Plat, TestCuisson

NOMBRE_MIS_EN_AVANT = 6


class AccueilView(TemplateView):
    """Page d'accueil.

    Les plats ne sont mis en avant que pour les membres connectés : le carnet
    est familial, rien n'est exposé aux visiteurs de passage.
    """

    template_name = "principal/accueil.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        if not self.request.user.is_authenticated:
            return contexte

        plats = Plat.objects.visibles().avec_details().avec_favori(self.request.user)
        contexte["plats_avec_meilleure_combinaison"] = plats.avec_meilleur_test().recents()[
            :NOMBRE_MIS_EN_AVANT
        ]
        contexte["plats_mieux_notes"] = plats.mieux_notes()[:NOMBRE_MIS_EN_AVANT]
        contexte["plats_recents"] = plats.recents()[:NOMBRE_MIS_EN_AVANT]
        return contexte


class TableauDeBordView(LoginRequiredMixin, TemplateView):
    """Le carnet en chiffres.

    Tous les compteurs sont calculés à la demande, jamais stockés : une
    statistique dénormalisée finit toujours par mentir.
    """

    template_name = "principal/tableau_de_bord.html"
    extra_context = {"rubrique": "tableau_de_bord"}

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        plats = Plat.objects.visibles()

        contexte["nombre_de_plats"] = plats.count()
        contexte["nombre_d_essais"] = TestCuisson.objects.count()
        contexte["nombre_au_point"] = plats.avec_meilleur_test().count()
        contexte["nombre_a_regler"] = plats.filter(meilleur_test__isnull=True).count()

        contexte["qui_cuisine"] = self.qui_cuisine()
        contexte["temperatures"] = self.temperatures_utilisees()
        contexte["derniers_essais"] = (
            TestCuisson.objects.select_related("plat", "plat__proprietaire")
            .order_by("-date_test", "-id")[:5]
        )
        contexte["mes_plats"] = (
            Plat.objects.de(self.request.user).avec_details().recents()[:NOMBRE_MIS_EN_AVANT]
        )
        contexte["mes_plats_total"] = Plat.objects.de(self.request.user).count()
        return contexte

    def qui_cuisine(self):
        """Répartition des essais par membre, avec la part de chacun."""
        repartition = list(
            TestCuisson.objects.values("plat__proprietaire__prenom", "plat__proprietaire__email")
            .annotate(total=Count("id"))
            .order_by("-total")[:5]
        )
        maximum = max((ligne["total"] for ligne in repartition), default=0)
        for ligne in repartition:
            ligne["nom"] = ligne["plat__proprietaire__prenom"] or ligne["plat__proprietaire__email"]
            ligne["part"] = round(ligne["total"] / maximum * 100) if maximum else 0
        return repartition

    def temperatures_utilisees(self):
        """Températures les plus employées, tous essais confondus."""
        repartition = list(
            TestCuisson.objects.values("temperature_celsius")
            .annotate(total=Count("id"))
            .order_by("-total", "-temperature_celsius")[:5]
        )
        maximum = max((ligne["total"] for ligne in repartition), default=0)
        for ligne in repartition:
            ligne["part"] = round(ligne["total"] / maximum * 100) if maximum else 0
        return repartition
