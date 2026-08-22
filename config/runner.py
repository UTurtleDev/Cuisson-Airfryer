"""Lanceur de tests du projet.

Le hachage des mots de passe est volontairement lent en production : c'est ce
qui protège les comptes. En test, cette lenteur se paie sur chaque compte créé
et n'apporte rien. On bascule donc sur un hachage rapide, uniquement pendant
les tests.
"""

from django.conf import settings
from django.test.runner import DiscoverRunner


class CoureurDeTests(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
