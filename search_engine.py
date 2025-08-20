# ================================================================================
# FICHIER: search_engine.py - Moteur de recherche principal
# ================================================================================
"""
Moteur de recherche avancé pour le BTP, qui intègre désormais un correcteur
orthographique pour améliorer la pertinence des résultats.
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
from corrector import Corrector # <-- IMPORT DU NOUVEAU MODULE

@dataclass
class SearchResult:
    """Structure de données pour un résultat de recherche."""
    designation: str
    prix: str
    unite: str
    score: float
    match_type: str
    matched_terms: List[str]
    num_matches: int

class BTCSearchEngine:
    """Moteur de recherche avancé pour le BTP."""
    
    def __init__(self, model_name: str = MODEL_CONFIG['name']):
        self.model = SentenceTransformer(model_name)
        self.text_processor = TextProcessor()
        self.dictionary_manager = DictionaryManager()
        self.corrector = Corrector() # <-- INITIALISATION DU CORRECTEUR
        logging.info(f"Moteur de recherche initialisé avec le modèle '{model_name}'.")

    def _get_flexible_matches(self, query_tokens: Set[str], designation_tokens: Set[str]) -> Set[str]:
        """
        Trouve les correspondances flexibles en utilisant startswith.
        """
        matches = set()
        for q_token in query_tokens:
            for d_token in designation_tokens:
                if d_token.startswith(q_token) or q_token.startswith(d_token):
                    matches.add(q_token)
                    break
        return matches

    def search(self, df: pd.DataFrame, query: str, limit: int = 20) -> List[dict]:
        """
        Effectue une recherche optimisée après avoir corrigé la requête.
        """
        if not query or len(query.strip()) < 2:
            return []

        # --- NOUVELLE ÉTAPE : CORRECTION DE LA REQUÊTE ---
        corrected_query = self.corrector.correct_query(query)
        
        query_norm = self.text_processor.normalize_text(corrected_query)
        query_tokens = set(self.text_processor.tokenize_btp(query_norm, preserve_technical=False))
        num_query_tokens = len(query_tokens)
        
        if not query_tokens:
            return []

        # Pré-traitement des désignations
        df['norm_designation'] = df['Désignation'].apply(self.text_processor.normalize_text)
        df['designation_tokens'] = df['norm_designation'].apply(
            lambda x: set(self.text_processor.tokenize_btp(x, preserve_technical=True))
        )

        # --- Étape 1: Construire la liste D1 ---
        results_d1 = []
        for index, row in df.iterrows():
            matches = self._get_flexible_matches(query_tokens, row['designation_tokens'])
            if matches:
                score = len(matches) * 10
                if query_tokens.intersection(row['designation_tokens']):
                    score += 5

                results_d1.append(SearchResult(
                    designation=row['Désignation'], prix=row['Prix'], unite=row['Unité'],
                    score=score, match_type='Mots-clés partiels (D1)', matched_terms=list(matches),
                    num_matches=len(matches)
                ))
        
        if not results_d1:
            logging.info("Aucun résultat partiel (D1) trouvé. Passage au Niveau 3 (D3).")
        else:
            # --- Étape 2: Logique de filtrage D2 ---
            if num_query_tokens > 1:
                results_d2 = [r for r in results_d1 if r.num_matches == num_query_tokens]
                
                if results_d2:
                    logging.info(f"Niveau 1 (D2): {len(results_d2)} résultat(s) parfait(s) trouvé(s).")
                    for r in results_d2:
                        r.score += 50
                        r.match_type = 'Tous les mots-clés (D2)'
                    results_d2.sort(key=lambda r: r.score, reverse=True)
                    return [asdict(r) for r in results_d2[:limit]]

            logging.info(f"Retourne {len(results_d1)} résultat(s) partiel(s) (D1).")
            results_d1.sort(key=lambda r: r.score, reverse=True)
            return [asdict(r) for r in results_d1[:limit]]

        # --- Étape 3 (D3): Recherche par synonymes ---
        expanded_terms = set(self.dictionary_manager.expand_query(corrected_query))
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
                    score=score, match_type='Synonymes (D3)', matched_terms=list(matches),
                    num_matches=len(matches)
                ))

        if results_d3:
            logging.info(f"Niveau 3 (D3): {len(results_d3)} résultat(s) trouvé(s).")
            results_d3.sort(key=lambda r: r.score, reverse=True)
            return [asdict(r) for r in results_d3[:limit]]

        logging.info("Aucun résultat trouvé après toutes les étapes.")
        return []
