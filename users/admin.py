from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

from users.models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """Administration des comptes, adaptée au modèle Utilisateur."""

    change_password_form = AdminPasswordChangeForm
    ordering = ["email"]
    list_display = ["email", "prenom", "nom", "is_active", "is_staff", "date_inscription"]
    list_filter = ["is_active", "is_staff", "is_superuser", "date_inscription"]
    search_fields = ["email", "prenom", "nom"]
    readonly_fields = ["last_login", "date_inscription"]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Informations personnelles", {"fields": ["prenom", "nom"]}),
        (
            "Droits",
            {
                "fields": [
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ]
            },
        ),
        ("Dates", {"fields": ["last_login", "date_inscription"]}),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["email", "prenom", "nom", "usable_password", "password1", "password2"],
            },
        ),
    ]
