"""
conftest.py — Sprint 1
=======================
Placé à la racine de sprint1/, ce fichier dit à pytest
que sprint1/ est la racine du projet Python.

Cela permet aux imports comme :
    from agents.context_sector_agent import ...
    from agents.nlq_agent import ...
    from api.main import app

de fonctionner depuis n'importe quel sous-dossier (tests/, etc.)
sans avoir à modifier le PYTHONPATH manuellement.
"""
import sys
import os

# Ajoute sprint1/ au PYTHONPATH automatiquement pour tous les tests
sys.path.insert(0, os.path.dirname(__file__))
