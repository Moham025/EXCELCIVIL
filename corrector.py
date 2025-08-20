# ================================================================================
# FICHIER: corrector.py - Correcteur orthographique simple
# ================================================================================
"""
Ce module gère la correction des fautes de frappe dans les requêtes de recherche
en se basant sur un dictionnaire de corrections défini dans un fichier JSON.
"""
import json
import logging
from pathlib import Path

# Import des modules locaux
from config import PATHS
from text_processor import TextProcessor

class Corrector:
    """Charge un dictionnaire de corrections et corrige les requêtes."""

    def __init__(self, corrections_path: Path = PATHS['base_dir'] / 'corrections.json'):
        self.corrections_path = corrections_path
        self.correction_map = self._load_corrections()

    def _load_corrections(self) -> dict:
        """
        Charge le fichier JSON et crée un dictionnaire inversé pour une recherche rapide.
        Ex: {"semell": "semelle", "semelles": "semelle"}
        """
        correction_map = {}
        try:
            with open(self.corrections_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Construit le dictionnaire inversé
            for correct_word, variations in data.items():
                for variation in variations:
                    # Normalise la variation pour la recherche
                    norm_variation = TextProcessor.normalize_text(variation)
                    correction_map[norm_variation] = correct_word
            
            logging.info(f"Dictionnaire de corrections chargé avec {len(correction_map)} variations.")
            return correction_map

        except (FileNotFoundError, json.JSONDecodeError):
            logging.warning(f"Fichier de corrections '{self.corrections_path}' non trouvé ou invalide. Aucune correction ne sera appliquée.")
            return {}

    def correct_query(self, query: str) -> str:
        """
        Prend une requête, la décompose en mots et corrige chaque mot si nécessaire.
        """
        if not self.correction_map:
            return query

        query_norm = TextProcessor.normalize_text(query)
        query_tokens = query_norm.split()
        
        corrected_tokens = []
        for token in query_tokens:
            # Si le mot est dans notre dictionnaire de fautes, on le remplace par le mot correct
            corrected_tokens.append(self.correction_map.get(token, token))
            
        corrected_query = ' '.join(corrected_tokens)
        
        if query != corrected_query:
            logging.info(f"Requête corrigée: '{query}' -> '{corrected_query}'")
            
        return corrected_query
