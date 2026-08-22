from django.contrib.auth.mixins import LoginRequiredMixin


class ProprietaireRequisMixin(LoginRequiredMixin):
    """Restreint la vue aux objets appartenant à l'utilisateur connecté.

    Le filtrage se fait dans le queryset : un plat qui ne lui appartient pas
    devient introuvable (404) plutôt qu'interdit (403). On ne révèle donc rien
    de plus que ce que l'utilisateur peut déjà voir.
    """

    champ_proprietaire = "proprietaire"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.champ_proprietaire: self.request.user})


class PlatProprietaireRequisMixin(ProprietaireRequisMixin):
    """Même principe, pour les objets rattachés à un plat (tests de cuisson)."""

    champ_proprietaire = "plat__proprietaire"
