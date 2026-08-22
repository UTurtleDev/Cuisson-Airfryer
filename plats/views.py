from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from plats.forms import FormulairePlat
from plats.mixins import ProprietaireRequisMixin
from plats.models import Plat


class ListePlatsView(LoginRequiredMixin, ListView):
    """Liste des plats de tous les membres."""

    model = Plat
    context_object_name = "plats"
    paginate_by = 12
    template_name = "plats/liste.html"

    def get_queryset(self):
        return Plat.objects.visibles().avec_details()


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
