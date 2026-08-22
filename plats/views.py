from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from plats.forms import FormulaireFiltrePlats, FormulairePlat, FormulaireTestCuisson
from plats.mixins import PlatProprietaireRequisMixin, ProprietaireRequisMixin
from plats.models import Plat, TestCuisson


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
        queryset = Plat.objects.visibles().avec_details()
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
        return Plat.objects.de(self.request.user).avec_details()


class DetailPlatView(LoginRequiredMixin, DetailView):
    model = Plat
    context_object_name = "plat"
    template_name = "plats/detail.html"

    def get_queryset(self):
        return Plat.objects.visibles().avec_details()

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["tests"] = self.object.tests.all()
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
                {"plat": plat, "tests": plat.tests.all(), "est_proprietaire": True},
            )
        return redirect(plat.get_absolute_url())
