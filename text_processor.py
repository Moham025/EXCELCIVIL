# ================================================================================
# FICHIER: text_processor.py - Traitement de texte avancé
# ================================================================================
"""
Module de traitement de texte spécialisé pour le domaine du BTP.
Fournit des outils pour normaliser, tokeniser et extraire des caractéristiques
techniques des textes de désignation.
"""
import re
from typing import List, Dict
import unicodedata

class TextProcessor:
    """Processeur de texte spécialisé pour le domaine BTP."""

    # Patterns Regex pour la reconnaissance d'entités techniques
    DOSAGE_PATTERN = re.compile(r'(\d+)\s*(kg/m[23]?|kg|l/m[23]?)', re.IGNORECASE)
    DIMENSION_PATTERN = re.compile(r'(\d+)\s*x\s*(\d+)(?:\s*x\s*(\d+))?', re.IGNORECASE)
    MEASUREMENT_PATTERN = re.compile(r'(\d+(?:[.,]\d+)?)\s*(m[23]?|cm|mm|kg|l|ml|cl)', re.IGNORECASE)

    # Mots vides (stop words) spécifiques au contexte BTP
    STOP_WORDS_BTP = {
        'de', 'la', 'le', 'et', 'en', 'un', 'une', 'avec', 'du', 'des', 'les',
        'pour', 'sur', 'dans', 'par', 'au', 'aux', 'ce', 'ces', 'son', 'sa',
        'y', 'compris'
    }

    # Dictionnaire d'abréviations techniques pour l'expansion
    ABBREVIATIONS_BTP = {
        'allu': 'aluminium', 'alu': 'aluminium', 'galva': 'galvanisé',
        'metal': 'métallique', 'm2': 'mètre carré', 'm3': 'mètre cube',
        'cm': 'centimètre', 'mm': 'millimètre', 'kg': 'kilogramme',
        'ep': 'épaisseur', 'dim': 'dimension', 'ht': 'hauteur',
        'lg': 'longueur', 'larg': 'largeur', 'prof': 'profondeur',
        'diam': 'diamètre', 'epaiss': 'épaisseur', 'bat': 'bâtiment',
        'elec': 'électricité', 'plomb': 'plomberie', 'menuis': 'menuiserie'
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalise un texte : accents, casse, et caractères spéciaux."""
        if not isinstance(text, str):
            return ""
        # Normalisation Unicode pour décomposer les caractères accentués
        text = unicodedata.normalize('NFD', text.lower())
        # Suppression des caractères diacritiques (accents)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        return text

    @staticmethod
    def extract_technical_features(text: str) -> Dict[str, list]:
        """Extrait les caractéristiques techniques (dosages, dimensions, etc.) d'un texte."""
        features = {
            'dosages': [],
            'dimensions': [],
            'measurements': [],
        }
        
        # Remplace les virgules par des points pour les nombres décimaux
        text_normalized = text.replace(',', '.')

        # Extraction des dosages (ex: "150 kg/m3")
        dosages = TextProcessor.DOSAGE_PATTERN.findall(text_normalized)
        features['dosages'] = [(float(val), unit.lower()) for val, unit in dosages]

        # Extraction des dimensions (ex: "20x40x60")
        dimensions = TextProcessor.DIMENSION_PATTERN.findall(text_normalized)
        features['dimensions'] = [tuple(filter(None, dim)) for dim in dimensions]

        # Extraction des mesures générales
        measurements = TextProcessor.MEASUREMENT_PATTERN.findall(text_normalized)
        features['measurements'] = [(float(val), unit.lower()) for val, unit in measurements]

        return features

    @staticmethod
    def tokenize_btp(text: str, preserve_technical: bool = True) -> List[str]:
        """Tokenisation intelligente qui préserve les termes techniques et gère les abréviations."""
        text = text.lower()

        # Expansion des abréviations avant la tokenisation
        for abbrev, full in TextProcessor.ABBREVIATIONS_BTP.items():
            text = re.sub(r'\b' + re.escape(abbrev) + r'\b', full, text)

        # Protège les termes techniques en remplaçant temporairement les espaces
        if preserve_technical:
            text = TextProcessor.DOSAGE_PATTERN.sub(lambda m: m.group(0).replace(' ', '_'), text)
            text = TextProcessor.DIMENSION_PATTERN.sub(lambda m: m.group(0).replace(' ', '_'), text)
            text = TextProcessor.MEASUREMENT_PATTERN.sub(lambda m: m.group(0).replace(' ', '_'), text)

        # Tokenisation : trouve les mots, y compris ceux avec des chiffres, '/', ou '_'
        tokens = re.findall(r'\b[\w/_-]+\b', text)

        # Restauration des espaces dans les termes protégés et filtrage
        filtered_tokens = []
        for token in tokens:
            token_restored = token.replace('_', ' ')
            # Garde les tokens s'ils ne sont pas des stop words ou s'ils contiennent des chiffres
            if token_restored not in TextProcessor.STOP_WORDS_BTP or any(char.isdigit() for char in token_restored):
                if len(token_restored) > 1:
                    filtered_tokens.append(token_restored)
        
        return filtered_tokens
