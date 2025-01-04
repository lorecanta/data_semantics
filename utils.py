# utils.py
import os
from huggingface_hub import hf_hub_download
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv()

def download_model_files(model_id, file_names, token):
    """
    Scarica i file associati a un modello specificato da Hugging Face Hub.
    
    Args:
        model_id (str): ID del modello su Hugging Face Hub.
        file_names (list): Elenco dei nomi dei file da scaricare.
        token (str): Token di autenticazione per l'accesso al modello.
    """
    for file in file_names:
        downloaded_model_path = hf_hub_download(
            repo_id=model_id,
            filename=file,
            token=token
        )
        print(f"Downloaded {file} to {downloaded_model_path}")

def download_model_files(model_id: str, model_files: str):
    """
    Scarica i file necessari per un modello specificato tramite Hugging Face Hub.

    Args:
    - model_id (str): l'ID del modello.
    - model_files (str): stringa con i nomi dei file separati da virgola.

    Restituisce una lista con i percorsi dei file scaricati.
    """
    downloaded_files = []
    for file_name in model_files.split(","):
        try:
            file_path = hf_hub_download(repo_id=model_id, filename=file_name)
            downloaded_files.append(file_path)
        except Exception as e:
            print(f"Errore nel download del file {file_name} per il modello {model_id}: {e}")
    return downloaded_files

def load_model_and_files(model_id: str, model_files: str):
    """
    Carica un modello e il tokenizer da Hugging Face Hub.

    Args:
    - model_id (str): l'ID del modello da caricare.
    - model_files (str): i file del modello da scaricare.

    Restituisce:
    - pipeline: pipeline per il riconoscimento entità (NER).
    """
    # Scarica i file necessari per il modello
    downloaded_files = download_model_files(model_id, model_files)

    # Carica il modello e il tokenizer dai file scaricati
    try:
        model = AutoModelForTokenClassification.from_pretrained(model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        return pipeline("ner", model=model, tokenizer=tokenizer)
    except Exception as e:
        print(f"Errore nel caricamento del modello {model_id}: {e}")
        return None

def get_model_details():
    """
    Restituisce gli ID dei modelli e i file associati dal file .env.
    """
    model_1_id = os.getenv("MODEL_1_ID")
    model_1_files = os.getenv("MODEL_1_FILES")

    model_2_id = os.getenv("MODEL_2_ID")
    model_2_files = os.getenv("MODEL_2_FILES")
    
    return (model_1_id, model_1_files), (model_2_id, model_2_files)

def reconstruct_word(tokens):
    """
    Combina i sub-token in parole complete, includendo gli score.
    
    Args:
    - tokens (list): lista di dizionari con i sub-token, contenenti le chiavi 'word', 'entity' e 'score'.
    
    Returns:
    - list: lista di parole complete con le relative entità e punteggi.
    """
    words = []
    current_word = ''
    current_entity = None
    current_score = None
    
    for token in tokens:
        word = token['word']
        entity = token['entity']
        score = token['score']
        
        # Se il sub-token è un sub-token (inizia con '##'), uniscilo con il token precedente
        if word.startswith('##'):
            current_word += word[2:]  # Rimuove '##' e aggiunge il sub-token
            current_score = max(current_score, score)  # Mantiene il punteggio massimo
        else:
            if current_word:
                # Aggiungi la parola finale con il punteggio associato
                words.append({'entity': current_entity, 'word': current_word, 'score': current_score})
            
            current_word = word
            current_entity = entity
            current_score = score  # Assegna il punteggio del nuovo token
            
    # Aggiungi l'ultimo token
    if current_word:
        words.append({'entity': current_entity, 'word': current_word, 'score': current_score})
    
    return words

def merge_results(model_1_results, model_2_results):
    """
    Unisce i risultati di due modelli, prendendo quella del modello 2 se una parola appare in entrambi.
    
    Args:
    - model_1_results (list): risultati del modello 1.
    - model_2_results (list): risultati del modello 2.
    
    Returns:
    - list: lista unita di parole con le relative entità e punteggi, preferendo i risultati del modello 2.
    """
    # Crea un dizionario per tenere traccia delle parole e dei loro risultati
    merged_dict = {}
    
    # Aggiungi i risultati del modello 1 nel dizionario (parola -> {entity, score})
    for result in model_1_results:
        merged_dict[result['word']] = {'entity': result['entity'], 'score': result['score']}
    
    # Aggiungi i risultati del modello 2, se la parola è già presente nel dizionario, sovrascrivi con il modello 2
    for result in model_2_results:
        merged_dict[result['word']] = {'entity': result['entity'], 'score': result['score']}
    
    # Crea la lista finale unita
    merged_results = [{'word': word, 'entity': values['entity'], 'score': values['score']} for word, values in merged_dict.items()]
    
    return merged_results