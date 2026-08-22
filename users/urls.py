from django.urls import path

from users import views

app_name = "users"

urlpatterns = [
    path("inscription/", views.InscriptionView.as_view(), name="inscription"),
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path(
        "mot-de-passe/changer/",
        views.ChangementMotDePasseView.as_view(),
        name="changement_mot_de_passe",
    ),
    path(
        "mot-de-passe/change/",
        views.ChangementMotDePasseEffectueView.as_view(),
        name="changement_mot_de_passe_effectue",
    ),
    path(
        "mot-de-passe/oublie/",
        views.ReinitialisationMotDePasseView.as_view(),
        name="reinitialisation",
    ),
    path(
        "mot-de-passe/oublie/envoye/",
        views.ReinitialisationEnvoyeeView.as_view(),
        name="reinitialisation_envoyee",
    ),
    path(
        "mot-de-passe/reinitialiser/<uidb64>/<token>/",
        views.ReinitialisationConfirmationView.as_view(),
        name="reinitialisation_confirmation",
    ),
    path(
        "mot-de-passe/reinitialiser/termine/",
        views.ReinitialisationTermineeView.as_view(),
        name="reinitialisation_terminee",
    ),
]
