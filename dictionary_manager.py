# ================================================================================
# FICHIER: dictionary_manager.py - Gestion du dictionnaire technique
# ================================================================================
"""
Gestionnaire pour le dictionnaire technique BTP.
Permet de charger, sauvegarder, et d'étendre les requêtes en utilisant des synonymes.
"""
import json
from typing import Dict, List, Set
from collections import defaultdict
import logging
from pathlib import Path

# Import des modules locaux
from text_processor import TextProcessor
from config import PATHS

class DictionaryManager:
    """Gestionnaire avancé du dictionnaire technique avec index inversé."""
    
    def __init__(self, dictionary_path: Path = PATHS['dictionary']):
        self.dictionary_path = dictionary_path
        self.dictionary: Dict[str, List[str]] = {}
        self.reverse_index: Dict[str, Set[str]] = defaultdict(set)
        self.load_dictionary()

    def load_dictionary(self):
        """Charge le dictionnaire depuis un fichier JSON."""
        try:
            with open(self.dictionary_path, 'r', encoding='utf-8') as f:
                self.dictionary = json.load(f)
            logging.info(f"Dictionnaire chargé depuis {self.dictionary_path} avec {len(self.dictionary)} entrées.")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"Fichier dictionnaire non trouvé ou invalide ({e}). Utilisation d'un dictionnaire vide.")
            self.dictionary = {}
        self._build_reverse_index()

    def save_dictionary(self):
        """Sauvegarde le dictionnaire dans un fichier JSON."""
        try:
            with open(self.dictionary_path, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, ensure_ascii=False, indent=4)
            logging.info(f"Dictionnaire sauvegardé dans {self.dictionary_path}.")
        except IOError as e:
            logging.error(f"Erreur lors de la sauvegarde du dictionnaire : {e}")

    def _build_reverse_index(self):
        """Construit un index inversé (synonyme -> terme principal) pour une recherche rapide."""
        self.reverse_index.clear()
        for main_term, synonyms in self.dictionary.items():
            # Normalise le terme principal et les synonymes pour l'index
            normalized_main_term = TextProcessor.normalize_text(main_term)
            for synonym in synonyms:
                normalized_synonym = TextProcessor.normalize_text(synonym)
                self.reverse_index[normalized_synonym].add(normalized_main_term)
        logging.info(f"Index inversé du dictionnaire construit avec {len(self.reverse_index)} clés.")

    def expand_query(self, query: str, max_expansions: int = 10) -> List[str]:
        """Étend une requête en y ajoutant des synonymes pertinents trouvés dans le dictionnaire."""
        normalized_query = TextProcessor.normalize_text(query)
        query_tokens = set(TextProcessor.tokenize_btp(normalized_query, preserve_technical=False))
        
        expanded_terms = set()
        
        # Ajoute les synonymes pour chaque token de la requête
        for token in query_tokens:
            if token in self.reverse_index:
                for main_term in self.reverse_index[token]:
                    # Ajoute tous les synonymes associés au terme principal
                    expanded_terms.update(self.dictionary.get(main_term, []))

        # Ajoute les termes originaux de la requête
        expanded_terms.update(query_tokens)
        
        # Limite le nombre de termes pour éviter une requête trop large
        return list(expanded_terms)[:max_expansions]

    def add_synonym(self, main_term: str, new_synonym: str):
        """Ajoute un nouveau synonyme à un terme existant ou crée une nouvelle entrée."""
        main_term_key = main_term.lower()
        
        # Si le terme principal n'existe pas, on le crée
        if main_term_key not in self.dictionary:
            self.dictionary[main_term_key] = [main_term]
        
        # Ajoute le nouveau synonyme s'il n'est pas déjà présent
        if new_synonym.lower() not in [s.lower() for s in self.dictionary[main_term_key]]:
            self.dictionary[main_term_key].append(new_synonym)
            logging.info(f"Ajout du synonyme '{new_synonym}' pour le terme '{main_term_key}'.")
            self._build_reverse_index()
            self.save_dictionary()
        else:
            logging.info(f"Le synonyme '{new_synonym}' existe déjà pour '{main_term_key}'.")
