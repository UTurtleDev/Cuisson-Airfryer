from django.db import migrations
from django.utils.text import slugify

# Liste de départ. Elle est ensuite gérable depuis l'administration :
# cette migration ne fait que poser les catégories initiales.
CATEGORIES_INITIALES = [
    "Viande",
    "Poisson",
    "Légumes",
    "Accompagnement",
    "Surgelé",
    "Apéritif",
    "Dessert",
]


def creer_categories(apps, schema_editor):
    Categorie = apps.get_model("plats", "Categorie")
    for ordre, nom in enumerate(CATEGORIES_INITIALES, start=1):
        Categorie.objects.get_or_create(
            nom=nom,
            defaults={"slug": slugify(nom), "ordre": ordre},
        )


def supprimer_categories(apps, schema_editor):
    Categorie = apps.get_model("plats", "Categorie")
    Categorie.objects.filter(nom__in=CATEGORIES_INITIALES).delete()


class Migration(migrations.Migration):
    dependencies = [("plats", "0001_initial")]

    operations = [migrations.RunPython(creer_categories, supprimer_categories)]
