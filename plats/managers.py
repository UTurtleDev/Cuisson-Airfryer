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
