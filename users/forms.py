from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm

from users.models import Utilisateur


class FormulaireInscription(BaseUserCreationForm):
    """Inscription d'un nouveau membre de la famille."""

    class Meta:
        model = Utilisateur
        fields = ["email", "prenom", "nom"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"autofocus": True, "autocomplete": "email"})
        self.fields["prenom"].help_text = "Facultatif."
        self.fields["nom"].help_text = "Facultatif."


class FormulaireConnexion(AuthenticationForm):
    """Connexion par adresse électronique."""

    username = forms.EmailField(
        label="Adresse électronique",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Adresse électronique ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }


class FormulaireProfil(forms.ModelForm):
    """Modification des informations personnelles."""

    class Meta:
        model = Utilisateur
        fields = ["email", "prenom", "nom"]
