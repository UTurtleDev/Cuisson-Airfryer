import sys
import os

# Ajouter le répertoire de votre projet au path Python
sys.path.insert(0, os.path.dirname(__file__))

# Importer les settings Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# Importer et configurer l'application WSGI
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()