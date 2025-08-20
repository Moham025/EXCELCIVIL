# ================================================================================
# FICHIER: app.py - Application Flask principale (Version Complète)
# ================================================================================
"""
Application web Flask servant de backend pour le système de recherche BTP.
Cette version inclut toutes les routes nécessaires pour une communication
complète avec le client Excel.
"""
import logging
import pandas as pd
import json
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pathlib import Path

# Import des modules et configurations locaux
from config import SERVER_CONFIG, PATHS
from search_engine import BTCSearchEngine
from dictionary_manager import DictionaryManager

# Configuration du logging pour un meilleur suivi
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Initialisation de l'application et des composants ---
app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False

logging.info("Initialisation du système de recherche BTP...")
search_engine = BTCSearchEngine()
dictionary_manager = DictionaryManager()

# Cache en mémoire pour les bibliothèques chargées
loaded_libraries: dict[str, pd.DataFrame] = {}
current_library_key: str | None = None

# --- Fonctions Utilitaires ---

def create_json_response(data, status_code=200):
    """Crée une réponse Flask en s'assurant que l'encodage est UTF-8."""
    json_string = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(json_string, content_type='application/json; charset=utf-8', status=status_code)

def get_available_libraries() -> list[str]:
    """Retourne la liste des noms de bibliothèques CSV disponibles."""
    if not PATHS['bibliotheque'].exists():
        return []
    return [p.stem for p in PATHS['bibliotheque'].glob("*.csv")]

def load_library(library_name: str, price_type: str = "Moyen") -> pd.DataFrame | None:
    """Charge une bibliothèque depuis un fichier CSV, la nettoie et calcule les embeddings."""
    global loaded_libraries, current_library_key
    cache_key = f"{library_name}_{price_type}"

    if cache_key in loaded_libraries:
        logging.info(f"Utilisation de la bibliothèque '{cache_key}' depuis le cache.")
        current_library_key = cache_key
        return loaded_libraries[cache_key]

    csv_path = PATHS['bibliotheque'] / f"{library_name}.csv"
    if not csv_path.exists():
        logging.error(f"Fichier bibliothèque introuvable : {csv_path}")
        return None

    try:
        logging.info(f"Chargement de la bibliothèque '{library_name}'...")
        column_names = ['Code', 'Désignation', 'Unité', 'Minimum', 'Moyen', 'Maximum', 'Extra']
        df = pd.read_csv(csv_path, encoding='utf-8', sep=';', skiprows=4, names=column_names, on_bad_lines='skip')
        
        df = df[['Désignation', 'Unité', price_type]].copy()
        df.rename(columns={price_type: 'Prix'}, inplace=True)
        df.dropna(subset=['Désignation'], inplace=True)

        df['Désignation'] = df['Désignation'].astype(str).str.strip()
        df['Unité'] = df['Unité'].astype(str).str.strip()
        df['Prix'] = df['Prix'].apply(lambda x: str(x).strip() if pd.notna(x) else "N/A")
        
        df = df[df['Désignation'].str.len() > 3].drop_duplicates(subset=['Désignation']).reset_index(drop=True)

        logging.info(f"Pré-calcul des embeddings pour {len(df)} articles...")
        df['embeddings'] = list(search_engine.model.encode(df['Désignation'].tolist(), show_progress_bar=True))
        
        loaded_libraries[cache_key] = df
        current_library_key = cache_key
        logging.info(f"Bibliothèque '{cache_key}' chargée avec {len(df)} articles.")
        return df

    except Exception as e:
        logging.error(f"Erreur lors du chargement de la bibliothèque '{library_name}': {e}")
        return None

# --- Endpoints de l'API ---

@app.route('/status', methods=['GET'])
def status():
    """Endpoint pour vérifier l'état du serveur."""
    return create_json_response({
        "status": "online",
        "current_library": current_library_key,
        "available_libraries": get_available_libraries(),
        "cached_libraries": list(loaded_libraries.keys()),
        "dictionary_entries": len(dictionary_manager.dictionary)
    })

@app.route('/libraries', methods=['GET'])
def list_libraries():
    """Liste les bibliothèques disponibles."""
    return create_json_response(get_available_libraries())

@app.route('/search', methods=['GET'])
def search():
    """Endpoint principal de recherche."""
    query = request.args.get('q', '').strip()
    library_name = request.args.get('library')
    price_type = request.args.get('price_type', 'Moyen')
    limit = int(request.args.get('limit', 20))

    if not library_name:
        return create_json_response({"error": "Le paramètre 'library' est requis."}, 400)

    df = load_library(library_name, price_type)
    if df is None:
        return create_json_response({"error": f"La bibliothèque '{library_name}' n'a pas pu être chargée."}, 404)

    results = search_engine.search(df, query, limit)
    return create_json_response(results)

# --- Démarrage du serveur ---

def load_startup_library():
    """Charge la bibliothèque de la dernière session ou une par défaut."""
    if PATHS['last_work'].exists():
        try:
            with open(PATHS['last_work'], 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) >= 3:
                    library_name = lines[1].strip()
                    price_type = lines[2].strip()
                    if load_library(library_name, price_type) is not None:
                        return
        except Exception as e:
            logging.error(f"Impossible de lire le fichier lastwork.txt : {e}")

    available_libs = get_available_libraries()
    if available_libs:
        load_library(available_libs[0])

if __name__ == '__main__':
    load_startup_library()
    logging.info(f"Démarrage du serveur Flask sur {SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}")
    app.run(host=SERVER_CONFIG['host'], port=SERVER_CONFIG['port'], debug=SERVER_CONFIG['debug'])
