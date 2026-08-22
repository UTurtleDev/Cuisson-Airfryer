"""Jeu de données de démonstration pour le développement local.

À lancer avec : python manage.py donnees_demo

Les comptes créés utilisent un mot de passe commun et volontairement visible :
ce sont des comptes de test locaux, jamais destinés à la production. La
commande refuse d'ailleurs de s'exécuter si DEBUG est désactivé.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from plats.models import Categorie, Plat, TestCuisson

Utilisateur = get_user_model()

MOT_DE_PASSE_DEMO = "cuisson-demo-2026"

MEMBRES = [
    ("sebastien@exemple.fr", "Sébastien", "Martin"),
    ("claire@exemple.fr", "Claire", "Martin"),
    ("lucas@exemple.fr", "Lucas", ""),
]

# (propriétaire, nom, description, catégories, personnes, préparation, tests)
# Un test : (température, durée, note, commentaire, jours avant aujourd'hui)
PLATS = [
    (
        0,
        "Hamburger maison",
        "Steak haché, cheddar, oignons confits.",
        ["Viande"],
        4,
        20,
        [
            (180, 12, 2, "Trop peu cuit au centre.", 40),
            (180, 15, 4, "Très bon, fondant.", 30),
            (190, 12, 5, "Excellent, bien saisi.", 20),
            (200, 10, 2, "Trop sec.", 10),
        ],
        2,
    ),
    (
        0,
        "Onion rings",
        "Surgelés, à sortir directement du congélateur.",
        ["Surgelé", "Apéritif"],
        2,
        2,
        [
            (200, 8, 4, "Bien croustillants.", 15),
            (180, 12, 3, "Corrects mais mous.", 25),
        ],
        0,
    ),
    (
        1,
        "Gnocchi au chorizo",
        "Gnocchi frais, chorizo doux, un filet d'huile.",
        ["Accompagnement"],
        4,
        10,
        [
            (190, 15, 4, "Gnocchi dorés, chorizo grillé.", 12),
            (200, 12, 3, "Un peu secs.", 5),
        ],
        0,
    ),
    (
        1,
        "Cordon bleu",
        "Surgelé, retourner à mi-cuisson.",
        ["Viande", "Surgelé"],
        2,
        1,
        [(180, 18, 5, "Parfait, fromage bien coulant.", 8)],
        0,
    ),
    (
        2,
        "Poulet entier",
        "Poulet fermier d'environ 1,3 kg.",
        ["Viande"],
        4,
        15,
        [
            (180, 65, 3, "Peau pas assez dorée.", 22),
            (190, 55, 4, "Mieux, mais un peu sec sur le blanc.", 9),
        ],
        None,
    ),
    (
        2,
        "Frites de patate douce",
        "Coupées en bâtonnets, un peu d'huile et du paprika.",
        ["Légumes", "Accompagnement"],
        3,
        10,
        [(200, 18, 4, "Croustillantes dehors, fondantes dedans.", 3)],
        0,
    ),
]


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration pour le développement local."

    def add_arguments(self, analyseur):
        analyseur.add_argument(
            "--reinitialiser",
            action="store_true",
            help="Supprime les plats et comptes de démonstration avant de les recréer.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Cette commande est réservée au développement (DEBUG doit être actif)."
            )

        if options["reinitialiser"]:
            emails = [email for email, _, _ in MEMBRES]
            Utilisateur.objects.filter(email__in=emails).delete()
            self.stdout.write("Anciennes données de démonstration supprimées.")

        membres = self.creer_membres()
        self.creer_plats(membres)

        self.stdout.write(self.style.SUCCESS("Jeu de démonstration prêt."))
        self.stdout.write("")
        self.stdout.write("Comptes disponibles :")
        for email, prenom, _ in MEMBRES:
            self.stdout.write(f"  {email}  ({prenom})")
        self.stdout.write(f"Mot de passe commun : {MOT_DE_PASSE_DEMO}")

    def creer_membres(self):
        membres = []
        for email, prenom, nom in MEMBRES:
            membre = Utilisateur.objects.filter(email=email).first()
            if membre is None:
                membre = Utilisateur.objects.creer_utilisateur(
                    email=email,
                    mot_de_passe=MOT_DE_PASSE_DEMO,
                    prenom=prenom,
                    nom=nom,
                )
            membres.append(membre)
        return membres

    def creer_plats(self, membres):
        aujourd_hui = timezone.localdate()

        for (
            index_membre,
            nom,
            description,
            categories,
            personnes,
            preparation,
            tests,
            index_meilleur,
        ) in PLATS:
            proprietaire = membres[index_membre]
            if Plat.objects.filter(nom=nom, proprietaire=proprietaire).exists():
                continue

            plat = Plat.objects.create(
                proprietaire=proprietaire,
                nom=nom,
                description=description,
                nombre_personnes=personnes,
                temps_preparation_minutes=preparation,
            )
            plat.categories.set(Categorie.objects.filter(nom__in=categories))

            crees = []
            for temperature, duree, note, commentaire, jours in tests:
                crees.append(
                    TestCuisson.objects.create(
                        plat=plat,
                        temperature_celsius=temperature,
                        duree_minutes=duree,
                        note=note,
                        commentaire=commentaire,
                        date_test=aujourd_hui - timedelta(days=jours),
                    )
                )

            # Volontairement, un plat reste sans meilleure combinaison :
            # la désignation est un choix humain, pas une conséquence des notes.
            if index_meilleur is not None:
                plat.definir_meilleur_test(crees[index_meilleur])

            self.stdout.write(f"  plat créé : {nom} ({len(crees)} test(s))")
