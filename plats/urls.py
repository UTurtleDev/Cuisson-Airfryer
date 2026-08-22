from django.urls import path

from plats import views

app_name = "plats"

urlpatterns = [
    path("", views.ListePlatsView.as_view(), name="liste"),
    path("mes-plats/", views.MesPlatsView.as_view(), name="mes_plats"),
    path("creer/", views.CreerPlatView.as_view(), name="creer"),
    path("favoris/", views.ListeFavorisView.as_view(), name="favoris"),
    path("<slug:slug>/", views.DetailPlatView.as_view(), name="detail"),
    path("<slug:slug>/modifier/", views.ModifierPlatView.as_view(), name="modifier"),
    path("<slug:slug>/supprimer/", views.SupprimerPlatView.as_view(), name="supprimer"),
    path("<slug:slug>/favori/", views.BasculerFavoriView.as_view(), name="basculer_favori"),
    path("<slug:slug>/copier/", views.CopierPlatView.as_view(), name="copier"),
    path("<slug:slug>/recette/", views.RecetteView.as_view(), name="recette"),
    path(
        "<slug:slug>/recette/modifier/",
        views.ModifierRecetteView.as_view(),
        name="modifier_recette",
    ),
    path("<slug:slug>/comparer/", views.ComparerTestsView.as_view(), name="comparer"),
    path("<slug:slug>/tests/ajouter/", views.CreerTestView.as_view(), name="creer_test"),
    path("tests/<int:pk>/modifier/", views.ModifierTestView.as_view(), name="modifier_test"),
    path("tests/<int:pk>/supprimer/", views.SupprimerTestView.as_view(), name="supprimer_test"),
    path(
        "tests/<int:pk>/meilleur/",
        views.DefinirMeilleurTestView.as_view(),
        name="definir_meilleur_test",
    ),
]
