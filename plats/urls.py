from django.urls import path

from plats import views

app_name = "plats"

urlpatterns = [
    path("", views.ListePlatsView.as_view(), name="liste"),
    path("mes-plats/", views.MesPlatsView.as_view(), name="mes_plats"),
    path("creer/", views.CreerPlatView.as_view(), name="creer"),
    path("<slug:slug>/", views.DetailPlatView.as_view(), name="detail"),
    path("<slug:slug>/modifier/", views.ModifierPlatView.as_view(), name="modifier"),
    path("<slug:slug>/supprimer/", views.SupprimerPlatView.as_view(), name="supprimer"),
]
