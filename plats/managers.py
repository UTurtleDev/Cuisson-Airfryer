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
        return self.select_related("proprietaire").prefetch_related("categories")

    def recherche(self, terme):
        if not terme:
            return self
        return self.filter(models.Q(nom__icontains=terme) | models.Q(description__icontains=terme))

    def par_categories(self, categories):
        if not categories:
            return self
        return self.filter(categories__in=categories).distinct()
