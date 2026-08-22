from django.db import models


class PlatQuerySet(models.QuerySet):
    """Requêtes réutilisables sur les plats.

    Les méthodes sont chaînables : elles se combinent librement pour construire
    la recherche et les filtres (lot 4).
    """

    def visibles(self):
        """Plats visibles par les membres : tous, l'application est familiale."""
        return self

    def de(self, utilisateur):
        return self.filter(proprietaire=utilisateur)

    def avec_details(self):
        """Précharge propriétaire et catégories pour éviter les requêtes N+1."""
        return self.select_related("proprietaire", "meilleur_test").prefetch_related(
            "categories"
        )

    def recherche(self, terme):
        if not terme:
            return self
        return self.filter(models.Q(nom__icontains=terme) | models.Q(description__icontains=terme))

    def preparation_maximum(self, minutes):
        """Filtre sur le temps de préparation renseigné du plat."""
        if not minutes:
            return self
        return self.filter(temps_preparation_minutes__lte=minutes)

    def avec_note_moyenne(self):
        """Annote la note moyenne et le nombre de tests de chaque plat."""
        return self.annotate(
            note_moyenne=models.Avg("tests__note"),
            nombre_tests=models.Count("tests", distinct=True),
        )

    def mieux_notes(self):
        """Plats ayant au moins un test, du mieux noté au moins bien noté."""
        return (
            self.avec_note_moyenne()
            .filter(note_moyenne__isnull=False)
            .order_by("-note_moyenne", "-date_creation")
        )

    def recents(self):
        return self.order_by("-date_creation")

    def favoris_de(self, utilisateur):
        """Plats mis en favori par ce membre, du plus récemment ajouté."""
        if not utilisateur.is_authenticated:
            return self.none()
        return self.filter(favoris__utilisateur=utilisateur).order_by("-favoris__date_ajout")

    def avec_favori(self, utilisateur):
        """Annote chaque plat d'un est_favori, en une seule requête.

        Sans cette annotation, l'affichage d'une liste interrogerait la base
        une fois par plat pour savoir s'il est en favori.
        """
        from plats.models import Favori

        if not utilisateur.is_authenticated:
            return self.annotate(
                est_favori=models.Value(False, output_field=models.BooleanField())
            )
        return self.annotate(
            est_favori=models.Exists(
                Favori.objects.filter(
                    plat=models.OuterRef("pk"), utilisateur=utilisateur
                )
            )
        )

    def avec_meilleur_test(self):
        """Ne garde que les plats dont la meilleure combinaison est désignée."""
        return self.filter(meilleur_test__isnull=False)

    def duree_cuisson_maximum(self, minutes):
        """Filtre sur la durée de la meilleure combinaison du plat.

        Les plats sans meilleure combinaison désignée sont écartés : sans
        elle, aucune durée ne fait référence.
        """
        if not minutes:
            return self
        return self.filter(meilleur_test__duree_minutes__lte=minutes)

    def par_categories(self, categories):
        if not categories:
            return self
        return self.filter(categories__in=categories).distinct()
