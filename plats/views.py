from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from plats.forms import FormulaireFiltrePlats, FormulairePlat, FormulaireTestCuisson
from plats.mixins import PlatProprietaireRequisMixin, ProprietaireRequisMixin
from plats.models import Plat, TestCuisson
from plats.services import CopieImpossible, basculer_favori, copier_plat


class ListePlatsView(LoginRequiredMixin, ListView):
    """Liste des plats de tous les membres, avec recherche et filtres.

    La même vue sert la page complète et, en HTMX, le seul fragment des
    résultats : inutile de reconstruire l'en-tête et le formulaire à chaque
    frappe.
    """

    model = Plat
    context_object_name = "plats"
    paginate_by = 12
    template_name = "plats/liste.html"
    template_name_fragment = "plats/partiels/liste_plats.html"

    def get_formulaire(self):
        if not hasattr(self, "_formulaire"):
            self._formulaire = FormulaireFiltrePlats(
                self.request.GET or None, utilisateur=self.request.user
            )
        return self._formulaire

    def get_queryset(self):
        queryset = Plat.objects.visibles().avec_details().avec_favori(self.request.user)
        formulaire = self.get_formulaire()
        if formulaire.is_bound and formulaire.is_valid():
            queryset = formulaire.filtrer(queryset, self.request.user)
        return queryset

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return [self.template_name_fragment]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["formulaire_filtres"] = self.get_formulaire()
        return contexte


class MesPlatsView(LoginRequiredMixin, ListView):
    """Liste des plats de l'utilisateur connecté."""

    model = Plat
    context_object_name = "plats"
    paginate_by = 12
    template_name = "plats/mes_plats.html"

    def get_queryset(self):
        return Plat.objects.de(self.request.user).avec_details().avec_favori(self.request.user)


class DetailPlatView(LoginRequiredMixin, DetailView):
    model = Plat
    context_object_name = "plat"
    template_name = "plats/detail.html"

    def get_queryset(self):
        return Plat.objects.visibles().avec_details().avec_favori(self.request.user)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["tests"] = self.object.tests_numerotes()
        contexte["est_proprietaire"] = self.object.appartient_a(self.request.user)
        return contexte


class CreerPlatView(LoginRequiredMixin, CreateView):
    model = Plat
    form_class = FormulairePlat
    template_name = "plats/formulaire.html"

    def form_valid(self, formulaire):
        formulaire.instance.proprietaire = self.request.user
        messages.success(self.request, "Plat créé.")
        return super().form_valid(formulaire)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre"] = "Nouveau plat"
        return contexte


class ModifierPlatView(ProprietaireRequisMixin, UpdateView):
    model = Plat
    form_class = FormulairePlat
    template_name = "plats/formulaire.html"

    def form_valid(self, formulaire):
        messages.success(self.request, "Plat modifié.")
        return super().form_valid(formulaire)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["titre"] = f"Modifier {self.object.nom}"
        return contexte


class SupprimerPlatView(ProprietaireRequisMixin, DeleteView):
    model = Plat
    context_object_name = "plat"
    template_name = "plats/confirmer_suppression.html"
    success_url = reverse_lazy("plats:mes_plats")

    def form_valid(self, formulaire):
        messages.success(self.request, "Plat supprimé.")
        return super().form_valid(formulaire)


class PlatDuMembreMixin(LoginRequiredMixin):
    """Récupère le plat de l'URL en exigeant qu'il appartienne au membre."""

    def setup(self, requete, *args, **kwargs):
        super().setup(requete, *args, **kwargs)
        self.plat = None

    def get_plat(self):
        if self.plat is None:
            self.plat = get_object_or_404(
                Plat, slug=self.kwargs["slug"], proprietaire=self.request.user
            )
        return self.plat


class CreerTestView(PlatDuMembreMixin, CreateView):
    """Ajout d'un essai de cuisson sur son propre plat."""

    model = TestCuisson
    form_class = FormulaireTestCuisson
    template_name = "plats/formulaire_test.html"

    def form_valid(self, formulaire):
        formulaire.instance.plat = self.get_plat()
        messages.success(self.request, "Test de cuisson enregistré.")
        return super().form_valid(formulaire)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["plat"] = self.get_plat()
        contexte["titre"] = f"Nouveau test - {self.get_plat().nom}"
        return contexte

    def get_success_url(self):
        return self.get_plat().get_absolute_url()


class ModifierTestView(PlatProprietaireRequisMixin, UpdateView):
    model = TestCuisson
    form_class = FormulaireTestCuisson
    template_name = "plats/formulaire_test.html"

    def form_valid(self, formulaire):
        messages.success(self.request, "Test de cuisson modifié.")
        return super().form_valid(formulaire)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["plat"] = self.object.plat
        contexte["titre"] = f"Modifier un test - {self.object.plat.nom}"
        return contexte

    def get_success_url(self):
        return self.object.plat.get_absolute_url()


class SupprimerTestView(PlatProprietaireRequisMixin, DeleteView):
    """Suppression d'un essai.

    Si le test supprimé était la meilleure combinaison, le plat n'en a plus :
    la clé étrangère est mise à NULL, le reste de l'historique est intact.
    """

    model = TestCuisson
    context_object_name = "test"
    template_name = "plats/confirmer_suppression_test.html"

    def form_valid(self, formulaire):
        messages.success(self.request, "Test de cuisson supprimé.")
        return super().form_valid(formulaire)

    def get_success_url(self):
        return self.object.plat.get_absolute_url()


class DefinirMeilleurTestView(PlatProprietaireRequisMixin, SingleObjectMixin, View):
    """Désigne, ou retire, la meilleure combinaison. Répond aussi en HTMX."""

    model = TestCuisson

    def post(self, requete, *args, **kwargs):
        test = self.get_object()
        plat = test.plat
        if test.est_meilleur:
            plat.definir_meilleur_test(None)
            messages.success(requete, "Meilleure combinaison retirée.")
        else:
            plat.definir_meilleur_test(test)
            messages.success(requete, "Meilleure combinaison mise à jour.")

        if requete.headers.get("HX-Request"):
            plat.refresh_from_db()
            return render(
                requete,
                "plats/partiels/historique.html",
                {"plat": plat, "tests": plat.tests_numerotes(), "est_proprietaire": True},
            )
        return redirect(plat.get_absolute_url())


class ComparerTestsView(LoginRequiredMixin, TemplateView):
    """Comparaison de plusieurs essais d'un même plat.

    La sélection arrive par l'URL (?test=1&test=2). Les identifiants qui ne
    correspondent pas à un test de ce plat sont simplement ignorés : la
    comparaison ne peut donc jamais mélanger deux plats.
    """

    template_name = "plats/comparaison.html"
    template_name_fragment = "plats/partiels/comparaison.html"
    MINIMUM_A_COMPARER = 2

    def get_plat(self):
        if not hasattr(self, "_plat"):
            self._plat = get_object_or_404(
                Plat.objects.visibles().avec_details(), slug=self.kwargs["slug"]
            )
        return self._plat

    def identifiants_demandes(self):
        """Identifiants valides passés dans l'URL, sans les valeurs fantaisistes."""
        return {
            int(valeur)
            for valeur in self.request.GET.getlist("test")
            if valeur.isdigit()
        }

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return [self.template_name_fragment]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        plat = self.get_plat()
        demandes = self.identifiants_demandes()

        # tests_numerotes conserve la numérotation des essais du plat entier,
        # et écarte au passage tout identifiant étranger au plat.
        selection = [test for test in plat.tests_numerotes() if test.pk in demandes]
        # Dans le tableau comparatif, on suit l'ordre des essais : #1, #2, #3.
        selection.sort(key=lambda test: test.numero)

        contexte["plat"] = plat
        contexte["tests"] = selection
        contexte["selection_insuffisante"] = len(selection) < self.MINIMUM_A_COMPARER
        contexte["minimum_a_comparer"] = self.MINIMUM_A_COMPARER
        contexte["note_maximum"] = max((test.note for test in selection), default=None)
        contexte["est_proprietaire"] = plat.appartient_a(self.request.user)
        return contexte


class ListeFavorisView(LoginRequiredMixin, ListView):
    """Plats mis de côté par le membre connecté."""

    model = Plat
    context_object_name = "plats"
    paginate_by = 12
    template_name = "plats/favoris.html"

    def get_queryset(self):
        return (
            Plat.objects.favoris_de(self.request.user)
            .avec_details()
            .avec_favori(self.request.user)
        )


class BasculerFavoriView(LoginRequiredMixin, SingleObjectMixin, View):
    """Ajoute ou retire un plat des favoris. Répond aussi en HTMX."""

    model = Plat

    def get_queryset(self):
        return Plat.objects.visibles()

    def post(self, requete, *args, **kwargs):
        plat = self.get_object()
        ajoute = basculer_favori(plat, requete.user)

        if requete.headers.get("HX-Request"):
            plat.est_favori = ajoute
            return render(requete, "plats/partiels/bouton_favori.html", {"plat": plat})

        messages.success(
            requete,
            "Plat ajouté à vos favoris." if ajoute else "Plat retiré de vos favoris.",
        )
        return redirect(plat.get_absolute_url())


class CopierPlatView(LoginRequiredMixin, SingleObjectMixin, View):
    """Crée sa propre version du plat d'un autre membre."""

    model = Plat

    def get_queryset(self):
        return Plat.objects.visibles()

    def post(self, requete, *args, **kwargs):
        plat = self.get_object()
        try:
            copie = copier_plat(plat, requete.user)
        except CopieImpossible as erreur:
            messages.error(requete, str(erreur))
            return redirect(plat.get_absolute_url())

        messages.success(
            requete,
            "Copie créée. Elle vous appartient, faites-en ce que vous voulez.",
        )
        return redirect(copie.get_absolute_url())
