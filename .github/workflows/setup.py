# setup.py (À placer dans votre repository partagé 'shared-utils')
from setuptools import setup

setup(
    name='my_shared_utils',
    version='0.1.0', # Utilisez une version pour la gestion
    py_modules=['utils'],  # Nom du fichier Python à inclure
    install_requires=[
        'streamlit',
        'pandas',
        'firebase-admin',
        'numpy',
        'python-docx', # Dépendance pour la génération de rapport Word
    ],
    # Si d'autres métadonnées sont utiles (auteur, description, etc.)
    description='Librairie de fonctions utilitaires partagées pour Streamlit.',
    author='Votre Nom',
)
