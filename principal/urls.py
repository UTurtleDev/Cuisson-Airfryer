from django.urls import path

from principal.views import AccueilView, TableauDeBordView

app_name = "principal"

urlpatterns = [
    path("", AccueilView.as_view(), name="accueil"),
    path("tableau-de-bord/", TableauDeBordView.as_view(), name="tableau_de_bord"),
]
