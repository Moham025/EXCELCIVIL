# ================================================================================
# FICHIER: search_engine.py - Moteur de recherche principal
# ================================================================================
"""
Moteur de recherche avancé pour le BTP, avec une logique de recherche
hiérarchisée et une gestion flexible du singulier/pluriel.
"""
import pandas as pd
from sentence_transformers import SentenceTransformer
from typing import List, Set
import logging
from dataclasses import dataclass, asdict

# Import des modules locaux
from config import MODEL_CONFIG
from text_processor import TextProcessor
from dictionary_manager import DictionaryManager

@dataclass
class SearchResult:
    """Structure de données pour un résultat de recherche."""
    designation: str
    prix: str
    unite: str
    score: float
    match_type: str
    matched_terms: List[str]

class BTCSearchEngine:
    """Moteur de recherche avancé pour le BTP."""
    
    def __init__(self, model_name: str = MODEL_CONFIG['name']):
        self.model = SentenceTransformer(model_name)
        self.text_processor = TextProcessor()
        self.dictionary_manager = DictionaryManager()
        logging.info(f"Moteur de recherche initialisé avec le modèle '{model_name}'.")

    def _get_flexible_matches(self, query_tokens: Set[str], designation_tokens: Set[str]) -> Set[str]:
        """
        Trouve les correspondances entre les tokens de la requête et de la désignation,
        en gérant les variations singulier/pluriel de manière bidirectionnelle.
        Ex: "puit" correspondra à "puits" et "puits" correspondra à "puit".
        """
        matches = set()
        for q_token in query_tokens:
            for d_token in designation_tokens:
                # La condition est maintenant bidirectionnelle pour une flexibilité maximale
                if q_token in d_token or d_token in q_token:
                    matches.add(q_token)
                    break  # On passe au mot-clé suivant dès qu'une correspondance est trouvée
        return matches

    def search(self, df: pd.DataFrame, query: str, limit: int = 20) -> List[dict]:
        """
        Effectue une recherche hiérarchisée en 3 niveaux : D2, D1, D3.
        """
        if not query or len(query.strip()) < 2:
            return []

        query_norm = self.text_processor.normalize_text(query)
        query_tokens = set(self.text_processor.tokenize_btp(query_norm, preserve_technical=False))
        
        if not query_tokens:
            return []

        # Pré-traitement de toutes les désignations une seule fois pour optimiser
        df['norm_designation'] = df['Désignation'].apply(self.text_processor.normalize_text)
        df['designation_tokens'] = df['norm_designation'].apply(
            lambda x: set(self.text_processor.tokenize_btp(x, preserve_technical=True))
        )

        # --- Niveau 1 (D2): Recherche des désignations contenant TOUS les mots-clés ---
        results_d2 = []
        for index, row in df.iterrows():
            matches = self._get_flexible_matches(query_tokens, row['designation_tokens'])
            
            if len(matches) == len(query_tokens):
                score = len(matches) * 50
                if query_norm in row['norm_designation']:
                    score += 25
                
                results_d2.append(SearchResult(
                    designation=row['Désignation'], prix=row['Prix'], unite=row['Unité'],
                    score=score, match_type='Tous les mots-clés (D2)', matched_terms=list(matches)
                ))
        
        if results_d2:
            logging.info(f"Niveau 1 (D2): {len(results_d2)} résultat(s) trouvé(s).")
            results_d2.sort(key=lambda r: r.score, reverse=True)
            return [asdict(r) for r in results_d2[:limit]]

        # --- Niveau 2 (D1): Recherche des désignations contenant AU MOINS UN mot-clé ---
        logging.info("Niveau 1 (D2) vide. Passage au Niveau 2 (D1).")
        results_d1 = []
        for index, row in df.iterrows():
            matches = self._get_flexible_matches(query_tokens, row['designation_tokens'])
            if matches:
                score = len(matches) * 10
                results_d1.append(SearchResult(
                    designation=row['Désignation'], prix=row['Prix'], unite=row['Unité'],
                    score=score, match_type='Mots-clés partiels (D1)', matched_terms=list(matches)
                ))

        if results_d1:
            logging.info(f"Niveau 2 (D1): {len(results_d1)} résultat(s) trouvé(s).")
            results_d1.sort(key=lambda r: r.score, reverse=True)
            return [asdict(r) for r in results_d1[:limit]]

        # --- Niveau 3 (D3): Recherche par synonymes ---
        logging.info("Niveau 2 (D1) vide. Passage au Niveau 3 (D3).")
        expanded_terms = set(self.dictionary_manager.expand_query(query))
        synonym_terms = expanded_terms - query_tokens

        if not synonym_terms:
            logging.info("Niveau 3 (D3): Aucun synonyme trouvé.")
            return []

        results_d3 = []
        for index, row in df.iterrows():
            matches = self._get_flexible_matches(synonym_terms, row['designation_tokens'])
            if matches:
                score = len(matches) * 5
                results_d3.append(SearchResult(
                    designation=row['Désignation'], prix=row['Prix'], unite=row['Unité'],
                    score=score, match_type='Synonymes (D3)', matched_terms=list(matches)
                ))

        if results_d3:
            logging.info(f"Niveau 3 (D3): {len(results_d3)} résultat(s) trouvé(s).")
            results_d3.sort(key=lambda r: r.score, reverse=True)
            return [asdict(r) for r in results_d3[:limit]]

        logging.info("Aucun résultat trouvé après les 3 niveaux de recherche.")
        return []
