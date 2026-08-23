from django import forms
from django.contrib.auth import get_user_model

from principal.formulaires import HabillageNocturneMixin

from plats.models import Categorie, EtapePreparation, Ingredient, Plat, TestCuisson

Utilisateur = get_user_model()


class FormulairePlat(HabillageNocturneMixin, forms.ModelForm):
    """Création et modification d'un plat."""

    ajouter_aux_favoris = forms.BooleanField(
        label="Ajouter à mes favoris",
        required=False,
    )

    categories = forms.ModelMultipleChoiceField(
        label="catégories",
        queryset=Categorie.objects.filter(est_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Plat
        fields = [
            "nom",
            "description",
            "image",
            "categories",
            "nombre_personnes",
            "temps_preparation_minutes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "image": "Facultative.",
            "temps_preparation_minutes": "Facultatif, en minutes.",
        }


class FormulaireTestCuisson(HabillageNocturneMixin, forms.ModelForm):
    """Enregistrement d'un essai de cuisson."""

    designer_comme_retenue = forms.BooleanField(
        label="Désigner comme combinaison retenue",
        required=False,
        initial=False,
        help_text="La combinaison retenue reste un choix explicite.",
    )

    class Meta:
        model = TestCuisson
        fields = ["temperature_celsius", "duree_minutes", "note", "commentaire", "date_test"]
        widgets = {
            "commentaire": forms.Textarea(attrs={"rows": 3}),
            "date_test": forms.DateInput(attrs={"type": "date"}),
            "temperature_celsius": forms.NumberInput(attrs={"min": 40, "max": 260, "step": 5}),
            "duree_minutes": forms.NumberInput(attrs={"min": 1, "max": 600}),
            "note": forms.RadioSelect,
        }
        help_texts = {
            "commentaire": "Trop cuit, pas assez doré, parfait…",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le segmenté n'a pas de case « aucune » : la note est obligatoire.
        self.fields["note"].empty_label = None
        self.fields["note"].choices = TestCuisson.Note.choices
        if self.instance.pk and self.instance.est_meilleur:
            self.fields["designer_comme_retenue"].initial = True


class FormulaireFiltrePlats(HabillageNocturneMixin, forms.Form):
    """Recherche et filtres de la liste des plats.

    Le formulaire porte lui-même la logique de filtrage : la vue reste courte
    et les filtres se combinent naturellement, chaque méthode du queryset
    renvoyant le queryset inchangé quand son critère est vide.
    """

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Hamburger, gnocchi…", "autocomplete": "off"}
        ),
    )
    categories = forms.ModelMultipleChoiceField(
        label="Catégories",
        queryset=Categorie.objects.filter(est_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    duree_maximum = forms.IntegerField(
        label="Cuisson maximum (minutes)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "20"}),
    )
    preparation_maximum = forms.IntegerField(
        label="Préparation maximum (minutes)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "15"}),
    )
    membre = forms.ChoiceField(label="Membre", required=False, choices=[])
    avec_meilleure_combinaison = forms.BooleanField(
        label="Avec une meilleure combinaison", required=False
    )
    favoris_uniquement = forms.BooleanField(label="Mes favoris", required=False)
    tri = forms.ChoiceField(
        label="Trier par",
        required=False,
        choices=[
            ("", "Essai le plus récent"),
            ("note", "Meilleure note"),
            ("nom", "Nom du plat"),
            ("essais", "Nombre d'essais"),
        ],
    )

    #: Valeur réservée pour « mes propres plats », les autres choix étant des pk.
    MOI = "moi"

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.utilisateur = utilisateur
        self.fields["membre"].choices = self.choix_de_membres()

    def choix_de_membres(self):
        """Construit la liste déroulante des membres.

        Seuls les membres actifs ayant au moins un plat y figurent : proposer
        un membre dont la liste serait vide n'apporterait rien.
        """
        choix = [("", "Tous les membres")]

        connecte = self.utilisateur is not None and self.utilisateur.is_authenticated
        if connecte:
            choix.append((self.MOI, "Seulement mes plats"))

        autres = Utilisateur.objects.filter(is_active=True, plats__isnull=False).distinct()
        if connecte:
            autres = autres.exclude(pk=self.utilisateur.pk)

        choix += [
            (str(membre.pk), membre.nom_affiche)
            for membre in autres.order_by("prenom", "nom", "email")
        ]
        return choix

    def filtrer(self, queryset, utilisateur):
        """Applique les critères renseignés, dans l'ordre, sur le queryset."""
        donnees = self.cleaned_data

        queryset = queryset.recherche(donnees.get("q"))
        queryset = queryset.par_categories(donnees.get("categories"))
        queryset = queryset.duree_cuisson_maximum(donnees.get("duree_maximum"))
        queryset = queryset.preparation_maximum(donnees.get("preparation_maximum"))

        membre = donnees.get("membre")
        if membre == self.MOI:
            queryset = queryset.de(utilisateur)
        elif membre:
            queryset = queryset.filter(proprietaire_id=membre)

        if donnees.get("avec_meilleure_combinaison"):
            queryset = queryset.avec_meilleur_test()
        if donnees.get("favoris_uniquement"):
            queryset = queryset.filter(favoris__utilisateur=utilisateur)

        return queryset.triee(donnees.get("tri"))


class FormulaireIngredient(HabillageNocturneMixin, forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ["nom", "quantite", "unite"]
        widgets = {
            "nom": forms.TextInput(attrs={"placeholder": "Farine"}),
            "quantite": forms.NumberInput(attrs={"placeholder": "250", "step": "0.01"}),
        }


class FormulaireEtape(HabillageNocturneMixin, forms.ModelForm):
    class Meta:
        model = EtapePreparation
        fields = ["texte"]
        widgets = {
            "texte": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Préchauffer l'Airfryer à 180 °C."}
            ),
        }


#: Formsets de la recette. L'ordre d'affichage vient de la position du
#: formulaire dans la page, l'utilisateur n'a pas de numéro à saisir.
JeuIngredients = forms.models.inlineformset_factory(
    Plat,
    Ingredient,
    form=FormulaireIngredient,
    extra=8,
    can_delete=True,
)

JeuEtapes = forms.models.inlineformset_factory(
    Plat,
    EtapePreparation,
    form=FormulaireEtape,
    extra=5,
    can_delete=True,
)


class FormulaireAdaptationRecette(HabillageNocturneMixin, forms.Form):
    """Choix du nombre de personnes pour l'affichage d'une recette."""

    personnes = forms.IntegerField(
        label="Pour combien de personnes",
        min_value=1,
        max_value=50,
        required=False,
    )
