"""Adaptation du pilote MySQL pour l'hébergement o2switch.

pymysql se fait passer pour MySQLdb, le pilote attendu par Django. Si pymysql
n'est pas installé (développement sur sqlite), on ne fait rien.
"""

try:
    import pymysql
except ImportError:  # pragma: no cover - sqlite en développement
    pass
else:
    pymysql.install_as_MySQLdb()
    # Contourne la vérification de version entre Django et MySQL.
    pymysql.version_info = (2, 2, 1, "final", 0)
