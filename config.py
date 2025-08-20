# ================================================================================
# FICHIER: config.py - Configuration centralisée
# ================================================================================
"""
Configuration centrale pour le système de recherche BTP.
Toutes les constantes et paramètres importants sont définis ici pour une gestion facile.
"""
import os
from pathlib import Path

# Configuration du serveur Flask
SERVER_CONFIG = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': False
}

# Configuration des chemins de l'application
PATHS = {
    'base_dir': Path(__file__).resolve().parent,
    'bibliotheque': Path(__file__).resolve().parent / "BIBLIOTHEQUE",
    'dictionary': Path(__file__).resolve().parent / 'technical_dictionary.json',
    'cache': Path('/tmp/cache'), # Changed from '/code/cache'
    'parametres': Path(__file__).resolve().parent / "parametres",
    'last_work': Path(__file__).resolve().parent / "parametres" / "lastwork.txt"
}

# Crée les dossiers nécessaires s'ils n'existent pas
PATHS['bibliotheque'].mkdir(exist_ok=True)
PATHS['cache'].mkdir(exist_ok=True)
PATHS['parametres'].mkdir(exist_ok=True)

# Configuration du modèle de Sentence Transformer
MODEL_CONFIG = {
    'name': 'all-MiniLM-L6-v2',
    'cache_embeddings': True
}

# ================================================================================
# == AJUSTEMENT DE LA PERTINENCE ==
# ================================================================================
# Seuils et poids pour l'algorithme de recherche.
# Ces valeurs ont été ajustées pour être plus strictes.
SEARCH_THRESHOLDS = {
    'keyword_min_score': 10,          # Augmenté de 5 à 10 pour être plus strict
    'keyword_high_confidence': 40,    # Augmenté de 25 à 40 pour ne garder que les meilleurs résultats
    'similarity_threshold': 0.55,     # Augmenté de 0.40 à 0.55 pour une similarité sémantique plus forte
    
    # --- Poids des différents critères (inchangés mais importants) ---
    'exact_match_boost': 50,
    'partial_match_boost': 6,
    'synonym_match_boost': 4,
    'position_boost': 8,
    'complete_match_boost': 25,
    'dosage_exact_boost': 30,
    'dosage_approx_boost': 15,
    'word_order_boost': 15,
    'length_penalty_short': 0.95,
    'length_penalty_long': 0.90,
}
