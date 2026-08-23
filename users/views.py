from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from users.forms import FormulaireConnexion, FormulaireInscription, FormulaireProfil
from plats.models import Plat, TestCuisson
from users.models import Utilisateur


class InscriptionView(CreateView):
    """Création d'un compte, suivie d'une connexion automatique."""

    model = Utilisateur
    form_class = FormulaireInscription
    template_name = "users/inscription.html"
    extra_context = {"rubrique": "inscription"}
    success_url = reverse_lazy("principal:tableau_de_bord")

    def form_valid(self, formulaire):
        reponse = super().form_valid(formulaire)
        login(self.request, self.object)
        messages.success(self.request, "Bienvenue, votre compte est créé.")
        return reponse


class ConnexionView(LoginView):
    template_name = "users/connexion.html"
    authentication_form = FormulaireConnexion
    redirect_authenticated_user = True

    def form_valid(self, formulaire):
        reponse = super().form_valid(formulaire)
        # Sans « rester connecté », la session tombe à la fermeture du
        # navigateur : utile sur un ordinateur partagé en famille.
        if not formulaire.cleaned_data.get("rester_connecte"):
            self.request.session.set_expiry(0)
        return reponse

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["nombre_de_plats"] = Plat.objects.count()
        contexte["nombre_d_essais"] = TestCuisson.objects.count()
        contexte["nombre_au_point"] = Plat.objects.avec_meilleur_test().count()
        return contexte


class DeconnexionView(LogoutView):
    """Déconnexion. Django n'accepte que la méthode POST."""

    next_page = reverse_lazy("principal:accueil")


class ProfilView(LoginRequiredMixin, UpdateView):
    """Modification du profil de l'utilisateur connecté."""

    model = Utilisateur
    form_class = FormulaireProfil
    template_name = "users/profil.html"
    success_url = reverse_lazy("users:profil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, formulaire):
        messages.success(self.request, "Profil mis à jour.")
        return super().form_valid(formulaire)


class ChangementMotDePasseView(LoginRequiredMixin, PasswordChangeView):
    template_name = "users/changement_mot_de_passe.html"
    success_url = reverse_lazy("users:changement_mot_de_passe_effectue")


class ChangementMotDePasseEffectueView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "users/changement_mot_de_passe_effectue.html"


class ReinitialisationMotDePasseView(PasswordResetView):
    template_name = "users/reinitialisation_demande.html"
    email_template_name = "users/courriels/reinitialisation.txt"
    subject_template_name = "users/courriels/reinitialisation_sujet.txt"
    success_url = reverse_lazy("users:reinitialisation_envoyee")


class ReinitialisationEnvoyeeView(PasswordResetDoneView):
    template_name = "users/reinitialisation_envoyee.html"


class ReinitialisationConfirmationView(PasswordResetConfirmView):
    template_name = "users/reinitialisation_confirmation.html"
    success_url = reverse_lazy("users:reinitialisation_terminee")


class ReinitialisationTermineeView(PasswordResetCompleteView):
    template_name = "users/reinitialisation_terminee.html"
