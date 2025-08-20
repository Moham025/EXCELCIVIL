import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from sentence_transformers import SentenceTransformer, util
import torch
import re
import json
import os
import glob

# --- Initialisation ---
app = Flask(__name__)
CORS(app)

app.config['JSON_AS_ASCII'] = False

app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

print("Chargement du modèle d'IA...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Modèle chargé.")

# --- Dictionnaire des termes techniques BTP ---
TECHNICAL_DICTIONARY = {}

# --- Dictionnaire des correspondances titres/sous-titres ---
TITLE_SUBTITLE_DICTIONARY = {}

# Variables globales pour les données hiérarchiques multi-CSV
loaded_csvs = {}  # Structure: {nom_fichier: {df_hierarchical, hierarchical_data, df_search}}

def load_title_subtitle_dictionary():
    """Charge le dictionnaire des correspondances titres/sous-titres."""
    global TITLE_SUBTITLE_DICTIONARY
    try:
        if os.path.exists('title_subtitle_dictionary.json'):
            with open('title_subtitle_dictionary.json', 'r', encoding='utf-8') as f:
                TITLE_SUBTITLE_DICTIONARY = json.load(f)
            print(f"Dictionnaire titres/sous-titres chargé : {len(TITLE_SUBTITLE_DICTIONARY)} entrées")
        else:
            # Créer le dictionnaire par défaut
            TITLE_SUBTITLE_DICTIONARY = {
                "BATIMENT NEUF": {
                    "patterns": ["BATIMENT", "NEUF", "REZ DE CHAUSSEE", "CONSTRUCTION"],
                    "subtitles": {
                        "TERRASSEMENT": ["INSTALLATION GENERALE DE CHANTIER", "TRAVAUX PREPARATOIRES ET TERRASSEMENT", "IMPLANTATION", "TERRASSEMENT GENERAL"],
                        "INFRASTRUCTURE": ["FONDATION", "SEMELLE", "RADIER", "SOUBASSEMENT", "INFRASTRUCTURE"],
                        "ELEVATION": ["SUPERSTRUCTURE", "MUR", "POTEAU", "POUTRE", "DALLE", "VOILE", "MACONNERIE"],
                        "TOITURE": ["CHARPENTE", "COUVERTURE", "TOITURE", "TUILE"],
                        "INSTALLATION & TERRASSEMENT": ["INSTALLATION GENERALE DE CHANTIER", "TRAVAUX PREPARATOIRES ET TERRASSEMENT"]
                    }
                },
                "REFECTION BATIMENT": {
                    "patterns": ["REFECTION", "RENOVATION", "REPARATION", "REHABILITATION"],
                    "subtitles": {
                        "TERRASSEMENT": ["REPRISE FONDATION", "TERRASSEMENT REFECTION"],
                        "INFRASTRUCTURE": ["CONSOLIDATION", "REPRISE INFRASTRUCTURE"],
                        "ELEVATION": ["REFECTION ELEVATION", "REPARATION MUR"],
                        "TOITURE": ["REFECTION TOITURE", "REPARATION CHARPENTE"],
                        "FINITION": ["ENDUIT", "CREPISSAGE", "PEINTURE", "REVETEMENT"]
                    }
                }
            }
            save_title_subtitle_dictionary()
    except Exception as e:
        print(f"Erreur chargement dictionnaire titres/sous-titres : {e}")

def save_title_subtitle_dictionary():
    """Sauvegarde le dictionnaire des correspondances titres/sous-titres."""
    with open('title_subtitle_dictionary.json', 'w', encoding='utf-8') as f:
        json.dump(TITLE_SUBTITLE_DICTIONARY, f, ensure_ascii=False, indent=2)

def load_dictionary():
    """Charge le dictionnaire technique depuis le fichier."""
    global TECHNICAL_DICTIONARY
    try:
        if os.path.exists('technical_dictionary.json'):
            with open('technical_dictionary.json', 'r', encoding='utf-8') as f:
                TECHNICAL_DICTIONARY = json.load(f)
            print(f"Dictionnaire technique chargé : {len(TECHNICAL_DICTIONARY)} entrées")
        else:
            # Dictionnaire par défaut (version abrégée)
            TECHNICAL_DICTIONARY = {
                "remblai": ["remblai", "remblayage", "comblement", "remplissage"],
                "terrassement": ["terrassement", "excavation", "deblai", "fouille"],
                "fouille": ["fouille", "excavation", "creusement", "terrassement"],
                "semelle": ["semelle", "fondation", "base"],
                "beton": ["beton", "mortier", "ciment"],
                "maconnerie": ["maconnerie", "construction", "batiment"],
                "peinture": ["peinture", "badigeon", "revetement", "finition", "FOM", "Enduit", "Peinture à eau", "Peinture", "Plâtre", "Phaum", "Faume"]
            }
            save_dictionary()
    except Exception as e:
        print(f"Erreur chargement dictionnaire technique : {e}")

def save_dictionary():
    """Sauvegarde le dictionnaire technique."""
    with open('technical_dictionary.json', 'w', encoding='utf-8') as f:
        json.dump(TECHNICAL_DICTIONARY, f, ensure_ascii=False, indent=2)

def parse_code_hierarchy(code):
    """Parse un code hiérarchique et retourne ses composants."""
    if not isinstance(code, str):
        return None
    
    parts = code.split('.')
    if len(parts) < 3:
        return None
    
    hierarchy = {
        "main": parts[0] if len(parts) > 0 else "",
        "title": parts[1] if len(parts) > 1 else "",
        "subtitle": parts[2] if len(parts) > 2 else "",
        "subsubtitle": parts[3] if len(parts) > 3 else "",
        "item": parts[4] if len(parts) > 4 else "",
        "detail": parts[5] if len(parts) > 5 else ""
    }
    
    return hierarchy

def identify_entry_type(designation, code):
    """Identifie si une entrée est un titre, sous-titre ou contenu."""
    if not isinstance(code, str):
        return "content"
    
    parts = code.split('.')
    
    # Titre principal (ex: 03.1.1)
    if len(parts) == 3 and parts[2] in ['0', '']:
        return "title"
    
    # Sous-titre (ex: 03.1.1.1)
    if len(parts) == 4 and parts[3] in ['0', '']:
        return "subtitle"
    
    # Contenu (ex: 03.1.1.1.0.001)
    if len(parts) >= 5:
        return "content"
    
    return "content"

def build_hierarchical_structure(df):
    """Construit une structure hiérarchique à partir du DataFrame."""
    structure = {}
    
    for idx, row in df.iterrows():
        code = str(row.get('Code', ''))
        designation = str(row.get('Désignation', ''))
        
        hierarchy = parse_code_hierarchy(code)
        if not hierarchy:
            continue
        
        entry_type = identify_entry_type(designation, code)
        
        # Clé pour le titre principal
        title_key = f"{hierarchy['main']}.{hierarchy['title']}.{hierarchy['subtitle']}"
        
        # Clé pour le sous-titre
        subtitle_key = f"{title_key}.{hierarchy['subsubtitle']}" if hierarchy['subsubtitle'] else title_key
        
        # Initialise la structure si nécessaire
        if title_key not in structure:
            structure[title_key] = {
                "title": "",
                "title_index": None,
                "subtitles": {},
                "content": []
            }
        
        if entry_type == "title":
            structure[title_key]["title"] = designation
            structure[title_key]["title_index"] = idx
            
        elif entry_type == "subtitle":
            if subtitle_key not in structure[title_key]["subtitles"]:
                structure[title_key]["subtitles"][subtitle_key] = {
                    "subtitle": designation,
                    "subtitle_index": idx,
                    "content": []
                }
            else:
                structure[title_key]["subtitles"][subtitle_key]["subtitle"] = designation
                structure[title_key]["subtitles"][subtitle_key]["subtitle_index"] = idx
                
        elif entry_type == "content":
            content_item = {
                "index": idx,
                "code": code,
                "designation": designation,
                "unite": row.get('Unité', ''),
                "minimum": row.get('Minimum', ''),
                "moyen": row.get('Moyen', ''),
                "maximum": row.get('Maximum', ''),
                "hierarchy": hierarchy
            }
            
            # Si c'est associé à un sous-titre
            if hierarchy['subsubtitle'] and subtitle_key in structure[title_key]["subtitles"]:
                structure[title_key]["subtitles"][subtitle_key]["content"].append(content_item)
            else:
                # Sinon, l'associer directement au titre
                structure[title_key]["content"].append(content_item)
    
    return structure

def find_matching_titles_in_csv(excel_titles, hierarchical_data):
    """Trouve les titres du CSV qui correspondent aux titres Excel sélectionnés."""
    matching_titles = []
    
    for excel_title in excel_titles:
        excel_title_upper = excel_title.upper()
        
        # Recherche directe dans le dictionnaire de correspondances
        if excel_title_upper in TITLE_SUBTITLE_DICTIONARY:
            title_config = TITLE_SUBTITLE_DICTIONARY[excel_title_upper]
            patterns = title_config.get("patterns", [])
            
            # Cherche dans les titres du CSV
            for title_key, title_data in hierarchical_data.items():
                csv_title = title_data.get("title", "").upper()
                
                # Correspondance par patterns
                for pattern in patterns:
                    if pattern.upper() in csv_title:
                        matching_titles.append({
                            "title_key": title_key,
                            "title_data": title_data,
                            "excel_title": excel_title
                        })
                        break
        
        # Recherche par correspondance partielle directe
        for title_key, title_data in hierarchical_data.items():
            csv_title = title_data.get("title", "").upper()
            
            # Correspondance partielle
            excel_words = excel_title_upper.split()
            for word in excel_words:
                if len(word) > 3 and word in csv_title:
                    matching_titles.append({
                        "title_key": title_key,
                        "title_data": title_data,
                        "excel_title": excel_title
                    })
                    break
    
    return matching_titles

def find_matching_subtitles_in_csv(excel_subtitle, excel_titles, hierarchical_data):
    """Trouve les sous-titres du CSV qui correspondent au sous-titre Excel."""
    matching_subtitles = []
    
    if not excel_subtitle:
        return matching_subtitles
    
    excel_subtitle_upper = excel_subtitle.upper()
    
    # Pour chaque titre Excel sélectionné
    for excel_title in excel_titles:
        excel_title_upper = excel_title.upper()
        
        # Cherche dans le dictionnaire de correspondances
        if excel_title_upper in TITLE_SUBTITLE_DICTIONARY:
            title_config = TITLE_SUBTITLE_DICTIONARY[excel_title_upper]
            subtitle_mapping = title_config.get("subtitles", {})
            
            # Trouve les sous-titres correspondants
            for subtitle_key, csv_subtitles in subtitle_mapping.items():
                if subtitle_key.upper() in excel_subtitle_upper or excel_subtitle_upper in subtitle_key.upper():
                    # Cherche ces sous-titres dans la structure hiérarchique
                    for title_key, title_data in hierarchical_data.items():
                        for subtitle_full_key, subtitle_data in title_data["subtitles"].items():
                            csv_subtitle = subtitle_data.get("subtitle", "").upper()
                            
                            for target_subtitle in csv_subtitles:
                                if target_subtitle.upper() in csv_subtitle:
                                    matching_subtitles.append({
                                        "title_key": title_key,
                                        "subtitle_key": subtitle_full_key,
                                        "subtitle_data": subtitle_data
                                    })
                                    break
    
    # Recherche directe par correspondance partielle si aucun résultat
    if not matching_subtitles:
        for title_key, title_data in hierarchical_data.items():
            for subtitle_key, subtitle_data in title_data["subtitles"].items():
                csv_subtitle = subtitle_data.get("subtitle", "").upper()
                
                # Correspondance par mots-clés
                excel_words = excel_subtitle_upper.split()
                for word in excel_words:
                    if len(word) > 3 and word in csv_subtitle:
                        matching_subtitles.append({
                            "title_key": title_key,
                            "subtitle_key": subtitle_key,
                            "subtitle_data": subtitle_data
                        })
                        break
    
    return matching_subtitles

def load_csv_file(filename):
    """Charge un fichier CSV spécifique."""
    file_path = os.path.join('BIBLIOTHEQUE', filename + '.csv')
    
    if not os.path.exists(file_path):
        print(f"ERREUR: Fichier '{file_path}' introuvable.")
        return None
    
    try:
        column_names = ['Code', 'Désignation', 'Unité', 'Minimum', 'Moyen', 'Maximum', 'Extra']
        
        df = pd.read_csv(file_path, encoding='utf-8', sep=';', skiprows=4, names=column_names)
        df_hierarchical = df[['Code', 'Désignation', 'Unité', 'Minimum', 'Moyen', 'Maximum']].copy()
        df_hierarchical.dropna(subset=['Désignation'], inplace=True)
        
        # Nettoyage des données
        df_hierarchical['Code'] = df_hierarchical['Code'].astype(str).str.strip()
        df_hierarchical['Désignation'] = df_hierarchical['Désignation'].astype(str).str.strip()
        df_hierarchical['Unité'] = df_hierarchical['Unité'].astype(str).str.strip()
        
        # Nettoyage des prix
        for price_col in ['Minimum', 'Moyen', 'Maximum']:
            df_hierarchical[price_col] = df_hierarchical[price_col].apply(clean_price)
        
        # Suppression des doublons
        df_hierarchical.drop_duplicates(subset=['Désignation', 'Unité'], inplace=True)
        df_hierarchical = df_hierarchical[df_hierarchical['Désignation'].str.len() > 3]
        
        print(f"Fichier {filename} chargé : {len(df_hierarchical)} articles")
        
        # Construction de la structure hiérarchique
        hierarchical_data = build_hierarchical_structure(df_hierarchical)
        
        # Préparation pour la recherche classique
        df_search = df_hierarchical[['Désignation', 'Unité', 'Minimum', 'Moyen', 'Maximum']].copy()
        df_search['search_text'] = df_search['Désignation'].apply(lambda x: preprocess_text(x, for_similarity=True))
        df_search = df_search[df_search['search_text'].str.len() > 0]
        df_search['embeddings'] = df_search['search_text'].apply(lambda x: model.encode(x))
        
        return {
            'df_hierarchical': df_hierarchical,
            'hierarchical_data': hierarchical_data,
            'df_search': df_search
        }
        
    except Exception as e:
        print(f"ERREUR lors du chargement de {filename}: {e}")
        return None

def load_all_csv_files():
    """Charge tous les fichiers CSV du dossier BIBLIOTHEQUE."""
    global loaded_csvs
    
    if not os.path.exists('BIBLIOTHEQUE'):
        print("ERREUR: Dossier 'BIBLIOTHEQUE' introuvable.")
        return
    
    csv_files = glob.glob('BIBLIOTHEQUE/*.csv')
    
    for file_path in csv_files:
        filename = os.path.splitext(os.path.basename(file_path))[0]
        print(f"Chargement de {filename}...")
        
        csv_data = load_csv_file(filename)
        if csv_data:
            loaded_csvs[filename] = csv_data
    
    print(f"Total fichiers CSV chargés : {len(loaded_csvs)}")

def expand_query(query):
    """Élargit la requête avec des synonymes techniques."""
    expanded_terms = set()
    query_lower = query.lower()
    
    for main_term, synonyms in TECHNICAL_DICTIONARY.items():
        for word in query_lower.split():
            word_clean = re.sub(r'[^\w]', '', word)
            if len(word_clean) < 3:
                continue
                
            if word_clean in [s.lower() for s in synonyms]:
                expanded_terms.update(synonyms)
            elif any(word_clean in s.lower() or s.lower() in word_clean for s in synonyms):
                expanded_terms.update(synonyms)
    
    original_words = [word for word in query_lower.split() if len(word) > 2]
    expanded_terms.update(original_words)
    
    return list(expanded_terms)

def calculate_relevance_score(designation, query_terms, expanded_terms):
    """Calcule un score de pertinence basé sur plusieurs critères."""
    designation_lower = designation.lower()
    score = 0
    
    for term in query_terms:
        if term in designation_lower:
            score += 10
            if re.search(r'\b' + re.escape(term) + r'\b', designation_lower):
                score += 5
    
    for term in expanded_terms:
        if term in designation_lower:
            score += 3
            if re.search(r'\b' + re.escape(term) + r'\b', designation_lower):
                score += 2

    if len(query_terms) > 1:
        num_original_matches = sum(1 for term in query_terms if term in designation_lower)
        if num_original_matches == len(query_terms):
            score += 20
    
    if len(designation) > 100:
        score -= 1
    
    if any(designation_lower.startswith(term) for term in query_terms + expanded_terms):
        score += 3
    
    return score

def preprocess_text(text, for_similarity=False):
    """Nettoie et standardise le texte."""
    if not isinstance(text, str):
        return ""
    
    text = text.lower()
    
    accents = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ô': 'o', 'ö': 'o',
        'ç': 'c',
        'î': 'i', 'ï': 'i'
    }
    
    for accent, letter in accents.items():
        text = text.replace(accent, letter)
    
    abbreviations = {
        r'\ballu\b': 'aluminium',
        r'\balu\b': 'aluminium',
        r'\bgalva\b': 'galvanise',
        r'\bmetal\b': 'metallique',
        r'\bm2\b': 'metre carre',
        r'\bm3\b': 'metre cube'
    }
    
    for abbrev, full in abbreviations.items():
        text = re.sub(abbrev, full, text)
    
    if for_similarity:
        stop_words = {'de', 'la', 'le', 'et', 'en', 'un', 'une', 'avec', 'du', 'des', 'les', 'pour', 'sur', 'dans', 'par'}
        words = text.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        return ' '.join(filtered_words)
    
    return text

def clean_price(price):
    """Nettoie et formate les prix."""
    if pd.isna(price):
        return "N/A"
    
    price_str = str(price).strip()
    
    try:
        price_float = float(price_str.replace(' ', ''))
        return f"{price_float:,.0f}".replace(',', ' ')
    except:
        return price_str

def get_price_by_type(content_item, price_type):
    """Retourne le prix selon le type demandé."""
    if price_type.upper() == "MINIMUM":
        return content_item.get('minimum', 'N/A')
    elif price_type.upper() == "MAXIMUM":
        return content_item.get('maximum', 'N/A')
    else:  # MOYEN par défaut
        return content_item.get('moyen', 'N/A')

# --- Chargement des dictionnaires et des données ---
load_dictionary()
load_title_subtitle_dictionary()
load_all_csv_files()

# --- API mise à jour ---
@app.route('/search', methods=['GET'])
def search():
    if not loaded_csvs:
        return jsonify({"error": "Aucun catalogue chargé."}), 500

    query = request.args.get('q', '').strip()
    csv_filename = request.args.get('csv', '').strip()
    price_type = request.args.get('price_type', 'Moyen').strip()
    titles_json = request.args.get('titles', '[]')
    subtitle = request.args.get('subtitle', '').strip()
    limit = int(request.args.get('limit', 20))
    
    print(f"--- Requête --- '{query}' | CSV: '{csv_filename}' | Prix: '{price_type}' | Sous-titre: '{subtitle}' | Limite: {limit}")
    
    if not query or len(query) < 2:
        return jsonify([])
    
    # Parse les titres sélectionnés
    try:
        selected_titles = json.loads(titles_json) if titles_json != '[]' else []
    except:
        selected_titles = []
    
    print(f"Titres sélectionnés: {selected_titles}")
    
    # Sélection du CSV
    if csv_filename and csv_filename in loaded_csvs:
        csv_data = loaded_csvs[csv_filename]
        print(f"Utilisation du CSV: {csv_filename}")
    else:
        # Prendre le premier CSV disponible
        if loaded_csvs:
            csv_filename = list(loaded_csvs.keys())[0]
            csv_data = loaded_csvs[csv_filename]
            print(f"CSV par défaut: {csv_filename}")
        else:
            return jsonify({"error": "Aucun CSV disponible"}), 500
    
    hierarchical_data = csv_data['hierarchical_data']
    df_search = csv_data['df_search']
    
    # --- Recherche hiérarchique si des filtres sont fournis ---
    search_scope = []
    
    if selected_titles or subtitle:
        print("Recherche avec filtres hiérarchiques...")
        
        # Recherche des titres correspondants
        if selected_titles:
            matching_titles = find_matching_titles_in_csv(selected_titles, hierarchical_data)
            print(f"Titres correspondants trouvés: {len(matching_titles)}")
            
            # Si on a aussi un sous-titre
            if subtitle:
                matching_subtitles = find_matching_subtitles_in_csv(subtitle, selected_titles, hierarchical_data)
                print(f"Sous-titres correspondants trouvés: {len(matching_subtitles)}")
                
                for subtitle_match in matching_subtitles:
                    subtitle_data = subtitle_match["subtitle_data"]
                    search_scope.extend(subtitle_data["content"])
            else:
                # Inclure tout le contenu des titres sélectionnés
                for title_match in matching_titles:
                    title_data = title_match["title_data"]
                    search_scope.extend(title_data["content"])
                    
                    # Inclure le contenu de tous les sous-titres
                    for subtitle_data in title_data["subtitles"].values():
                        search_scope.extend(subtitle_data["content"])
        
        elif subtitle:
            # Recherche de sous-titre sans titre spécifique
            for title_key, title_data in hierarchical_data.items():
                for subtitle_key, subtitle_data in title_data["subtitles"].items():
                    csv_subtitle = subtitle_data.get("subtitle", "").upper()
                    
                    subtitle_words = subtitle.upper().split()
                    for word in subtitle_words:
                        if len(word) > 3 and word in csv_subtitle:
                            search_scope.extend(subtitle_data["content"])
                            break
        
        print(f"Périmètre de recherche: {len(search_scope)} éléments")
    
    # Si aucun filtre ou aucune correspondance trouvée, recherche globale
    if not search_scope:
        print("Recherche globale...")
        return search_global(query, price_type, df_search, limit)
    
    # --- Recherche dans le périmètre restreint ---
    original_terms = [word.lower() for word in query.split() if len(word) > 2]
    expanded_terms = expand_query(query)
    
    print(f"Termes originaux: {original_terms}")
    print(f"Termes étendus: {expanded_terms}")
    
    results_with_scores = []
    
    for item in search_scope:
        designation = item['designation']
        relevance_score = calculate_relevance_score(designation, original_terms, expanded_terms)
        
        if relevance_score > 0:
            results_with_scores.append({
                'designation': designation,
                'prix': get_price_by_type(item, price_type),
                'unite': item['unite'],
                'code': item['code'],
                'score': relevance_score
            })
    
    # Tri des résultats
    results_with_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Formatage final
    suggestions = []
    for result in results_with_scores[:limit]:
        suggestions.append({
            "designation": result['designation'],
            "prix": result['prix'],
            "unite": result['unite'],
            "code": result.get('code', ''),
            "score": round(result['score'], 2)
        })
    
    print(f"--- Réponse hiérarchique --- {len(suggestions)} résultat(s)")

    response = app.response_class(
        response=json.dumps(suggestions, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )
    
    return response

def search_global(query, price_type, df_search, limit):
    """Fonction de recherche globale."""
    original_terms = [word.lower() for word in query.split() if len(word) > 2]
    expanded_terms = expand_query(query)
    
    results_with_scores = []
    
    for idx, row in df_search.iterrows():
        designation = row['Désignation']
        relevance_score = calculate_relevance_score(designation, original_terms, expanded_terms)
        
        if relevance_score > 0:
            # Sélection du prix selon le type
            if price_type.upper() == "MINIMUM":
                prix = row['Minimum']
            elif price_type.upper() == "MAXIMUM":
                prix = row['Maximum']
            else:
                prix = row['Moyen']
            
            results_with_scores.append({
                'index': idx,
                'designation': designation,
                'prix': prix,
                'unite': row['Unité'],
                'score': relevance_score
            })
    
    results_with_scores.sort(key=lambda x: x['score'], reverse=True)
    
    final_results = []

    if results_with_scores and results_with_scores[0]['score'] > 20:
        top_score = results_with_scores[0]['score']
        score_threshold = top_score * 0.5

        for result in results_with_scores:
            if result['score'] >= score_threshold:
                final_results.append(result)
            else:
                break
    else:
        final_results = results_with_scores
        
        try:
            processed_query = preprocess_text(' '.join(expanded_terms), for_similarity=True)
            if processed_query:
                query_embedding = model.encode(processed_query)
                
                found_indices = {r['index'] for r in final_results}
                remaining_df = df_search[~df_search.index.isin(found_indices)]
                
                similarities = []
                for idx, row in remaining_df.iterrows():
                    similarity = util.cos_sim(query_embedding, row['embeddings']).item()
                    if similarity > 0.35:
                        # Sélection du prix selon le type
                        if price_type.upper() == "MINIMUM":
                            prix = row['Minimum']
                        elif price_type.upper() == "MAXIMUM":
                            prix = row['Maximum']
                        else:
                            prix = row['Moyen']
                        
                        similarities.append({
                            'index': idx,
                            'designation': row['Désignation'],
                            'prix': prix,
                            'unite': row['Unité'],
                            'score': similarity * 10
                        })
                
                final_results.extend(similarities)
                final_results.sort(key=lambda x: x['score'], reverse=True)
        
        except Exception as e:
            print(f"Erreur durant la recherche par similarité: {e}")

    suggestions = []
    for result in final_results[:limit]:
        suggestions.append({
            "designation": result['designation'],
            "prix": result['prix'],
            "unite": result['unite'],
            "score": round(result['score'], 2)
        })
    
    print(f"--- Réponse globale --- {len(suggestions)} résultat(s)")

    response = app.response_class(
        response=json.dumps(suggestions, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )
    
    return response

# --- Route pour obtenir la liste des CSV disponibles ---
@app.route('/csv_files', methods=['GET'])
def get_csv_files():
    """Retourne la liste des fichiers CSV disponibles."""
    return jsonify({
        "files": list(loaded_csvs.keys()),
        "count": len(loaded_csvs)
    })

# --- Route pour obtenir la structure hiérarchique d'un CSV ---
@app.route('/hierarchy', methods=['GET'])
def get_hierarchy():
    """Retourne la structure hiérarchique d'un CSV."""
    csv_filename = request.args.get('csv', '').strip()
    
    if csv_filename and csv_filename in loaded_csvs:
        hierarchical_data = loaded_csvs[csv_filename]['hierarchical_data']
    else:
        if loaded_csvs:
            csv_filename = list(loaded_csvs.keys())[0]
            hierarchical_data = loaded_csvs[csv_filename]['hierarchical_data']
        else:
            return jsonify({"error": "Aucun CSV disponible"}), 500
    
    # Simplifier la structure pour l'envoi
    simplified_hierarchy = {}
    
    for title_key, title_data in hierarchical_data.items():
        simplified_hierarchy[title_key] = {
            "title": title_data.get("title", ""),
            "subtitles": {}
        }
        
        for subtitle_key, subtitle_data in title_data["subtitles"].items():
            simplified_hierarchy[title_key]["subtitles"][subtitle_key] = {
                "subtitle": subtitle_data.get("subtitle", "")
            }
    
    return jsonify({
        "csv": csv_filename,
        "hierarchy": simplified_hierarchy
    })

# --- Route pour recharger un CSV spécifique ---
@app.route('/reload_csv', methods=['POST'])
def reload_csv():
    """Recharge un fichier CSV spécifique."""
    data = request.get_json()
    filename = data.get('filename', '').strip()
    
    if not filename:
        return jsonify({"error": "Nom de fichier requis"}), 400
    
    csv_data = load_csv_file(filename)
    if csv_data:
        loaded_csvs[filename] = csv_data
        return jsonify({
            "status": "success",
            "message": f"Fichier {filename} rechargé",
            "articles": len(csv_data['df_hierarchical'])
        })
    else:
        return jsonify({"error": f"Impossible de charger {filename}"}), 500

# --- Routes pour gérer les dictionnaires ---
@app.route('/dictionary', methods=['GET'])
def get_dictionary():
    """Retourne le dictionnaire technique."""
    return jsonify(TECHNICAL_DICTIONARY)

@app.route('/dictionary', methods=['POST'])
def update_dictionary():
    """Met à jour le dictionnaire technique."""
    try:
        data = request.get_json()
        if 'term' in data and 'synonyms' in data:
            TECHNICAL_DICTIONARY[data['term']] = data['synonyms']
            save_dictionary()
            return jsonify({"status": "success", "message": "Dictionnaire mis à jour"})
        else:
            return jsonify({"error": "Format invalide"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/title_dictionary', methods=['GET'])
def get_title_dictionary():
    """Retourne le dictionnaire des correspondances titres/sous-titres."""
    return jsonify(TITLE_SUBTITLE_DICTIONARY)

@app.route('/title_dictionary', methods=['POST'])
def update_title_dictionary():
    """Met à jour le dictionnaire des correspondances titres/sous-titres."""
    try:
        data = request.get_json()
        if 'title' in data and 'config' in data:
            TITLE_SUBTITLE_DICTIONARY[data['title']] = data['config']
            save_title_subtitle_dictionary()
            return jsonify({"status": "success", "message": "Dictionnaire titres/sous-titres mis à jour"})
        else:
            return jsonify({"error": "Format invalide"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    """Route de test."""
    return jsonify({
        "status": "OK",
        "message": "Serveur fonctionnel",
        "csv_files_loaded": len(loaded_csvs),
        "csv_files": list(loaded_csvs.keys()),
        "dictionnaire_entries": len(TECHNICAL_DICTIONARY),
        "title_dictionary_entries": len(TITLE_SUBTITLE_DICTIONARY)
    })

@app.route('/count', methods=['GET'])
def count_results():
    """Compte le nombre total de résultats pour une requête."""
    if not loaded_csvs:
        return jsonify({"error": "Aucun catalogue chargé."}), 500

    query = request.args.get('q', '').strip()
    csv_filename = request.args.get('csv', '').strip()
    
    if not query:
        return jsonify({"count": 0})

    # Sélection du CSV
    if csv_filename and csv_filename in loaded_csvs:
        df_search = loaded_csvs[csv_filename]['df_search']
    else:
        if loaded_csvs:
            csv_filename = list(loaded_csvs.keys())[0]
            df_search = loaded_csvs[csv_filename]['df_search']
        else:
            return jsonify({"error": "Aucun CSV disponible"}), 500

    expanded_terms = expand_query(query)
    count = 0
    
    for _, row in df_search.iterrows():
        designation_lower = row['Désignation'].lower()
        if any(term in designation_lower for term in expanded_terms):
            count += 1
    
    return jsonify({
        "count": count, 
        "query": query, 
        "csv": csv_filename,
        "expanded_terms": expanded_terms
    })

if __name__ == '__main__':
    print("Serveur BTP optimisé avec recherche hiérarchique multi-CSV démarré sur http://127.0.0.1:5000")
    print("Routes disponibles:")
    print("- /search?q=terme&csv=fichier&price_type=Moyen&titles=[...]&subtitle=...&limit=20")
    print("- /csv_files")
    print("- /hierarchy?csv=fichier")
    print("- /reload_csv (POST)")
    print("- /count?q=terme&csv=fichier") 
    print("- /test")
    print("- /dictionary (GET/POST)")
    print("- /title_dictionary (GET/POST)")
    app.run(port=5000, debug=False, host='127.0.0.1')