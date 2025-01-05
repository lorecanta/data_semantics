# utils.py
import os
from huggingface_hub import hf_hub_download
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification, MarianMTModel, MarianTokenizer, AutoModelForSequenceClassification
from dotenv import load_dotenv
import re
import spacy

nlp = spacy.load("it_core_news_sm")

# Carica variabili d'ambiente dal file .env
load_dotenv()

def load_models():
    models = {}
    model_number = 1
    
    # Cerca le variabili MODEL_X_ID e MODEL_X_FILES nel file .env
    while True:
        model_id_key = f"MODEL_{model_number}_ID"
        model_files_key = f"MODEL_{model_number}_FILES"
        
        # Se le variabili non esistono, esci dal ciclo
        if model_id_key not in os.environ or model_files_key not in os.environ:
            break
        
        # Carica l'ID del modello e i relativi file
        model_id = os.getenv(model_id_key)
        model_files = os.getenv(model_files_key).split(",")
        
        # Aggiungi il modello al dizionario
        models[model_id] = model_files
        
        # Incrementa il numero del modello
        model_number += 1

    return models

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

def load_model_and_files(model_id: str, model_type: str = "ner"):
    """
    Carica un modello e il tokenizer da Hugging Face Hub.
    
    Args:
    - model_id (str): l'ID del modello da caricare.
    - model_type (str): il tipo di modello da caricare. Valori supportati:
        * "ner" per riconoscimento di entità.
        * "translation" per traduzione.
        * "classification" per classificazione del testo.
    
    Restituisce:
    - Una pipeline o una funzione di traduzione, a seconda del tipo di modello.
    """
    try:
        if model_type == "ner":
            # Carica il modello e tokenizer per NER
            model = AutoModelForTokenClassification.from_pretrained(model_id)
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            return pipeline("ner", model=model, tokenizer=tokenizer)
        
        elif model_type == "translation":
            # Carica il modello e tokenizer per traduzione
            model = MarianMTModel.from_pretrained(model_id)
            tokenizer = MarianTokenizer.from_pretrained(model_id)
            
            # Definizione di una funzione per eseguire la traduzione
            def translate_text(text):
                # Tokenizza il testo
                inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
                # Ottieni la traduzione
                translated = model.generate(**inputs)
                # Decodifica la traduzione
                return tokenizer.decode(translated[0], skip_special_tokens=True)
            
            return translate_text
        
        elif model_type == "classification":
            # Carica il modello e tokenizer per classificazione del testo
            model = AutoModelForSequenceClassification.from_pretrained(model_id)
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            # Restituisce una pipeline per classificazione del testo
            return pipeline(task="text-classification", model=model, tokenizer=tokenizer, top_k=None)
        
        else:
            raise ValueError(f"Tipo di modello '{model_type}' non supportato.")
    
    except Exception as e:
        print(f"Errore nel caricamento del modello {model_id}: {e}")
        return None

def get_model_details():
    load_dotenv()  # Carica le variabili dal file .env
    models = []
    for i in range(1, 5):  # Supponendo di avere 4 modelli
        model_id = os.getenv(f"MODEL_{i}_ID")
        model_type = os.getenv(f"MODEL_{i}_TYPE")
        model_files = os.getenv(f"MODEL_{i}_FILES")
        if model_id and model_type and model_files:
            models.append((model_id, model_type, model_files.split(',')))
    return models

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

def preprocess_text(text):
    """
    Preprocessa un testo per ottimizzare l'analisi tramite NER.
    Esegue:
    1. Conversione a minuscolo.
    2. Rimozione di emoji in formato `:nome_emoji:`.
    3. Rimozione di caratteri speciali e simboli, mantenendo punteggiatura utile.
    4. Sostituzione di spazi multipli con un singolo spazio.
    """
    # 1. Conversione a minuscolo
    text = text.lower()
    
    # 2. Rimozione di emoji in formato `:nome_emoji:`
    text = re.sub(r":\w+:", " ", text)
    
    # 3. Rimozione di caratteri speciali e simboli (mantieni punteggiatura utile)
    text = re.sub(r"[^\w\s.,!?']", " ", text)
    
    # 4. Sostituzione di spazi multipli con un singolo spazio
    text = re.sub(r"\s+", " ", text).strip()
    
    return text

def preprocess_stopwords(text):
    """
    Togli le stop-words, ma preserva gli apostrofi in espressioni composte.
    """
    doc = nlp(text)
    
    # Mantieni i token che non sono stopword e non sono apostrofi singoli
    processed_tokens = [token.text for token in doc if not token.is_stop or "'" in token.text]
    
    return " ".join(processed_tokens)

def preprocess_lemmatization(text):
    """
    Lemmatizza il testo mantenendo anche le stop-words e rimuovendo quelle 
    che non sono utili senza eliminarle tramite il `token.is_stop`. Se il lemma 
    è vuoto, mantieni la parola originale.
    """
    doc = nlp(text)
    
    # Mantieni tutte le parole, ma solo quelle non stop-words
    processed_tokens = [token.lemma_ if token.lemma_ != "-PRON-" else token.text for token in doc]
    
    # Se il lemma è vuoto o non valido, mantieni la parola originale
    processed_tokens = [token.lemma_ if token.lemma_ != "-PRON-" and token.lemma_ else token.text for token in doc]
    
    return " ".join(processed_tokens)


def traduci_output(output):
    """
    Traduce i label di emozioni da inglese a italiano nell'output di un modello.
    
    Args:
    - output (list): Lista contenente i dizionari con le emozioni e i punteggi.
    
    Restituisce:
    - list: Lista con i label tradotti in italiano.
    """
    # Dizionario di traduzione dei label direttamente nella funzione
    traduzione_label = {
        'desire': 'desiderio',
        'curiosity': 'curiosità',
        'optimism': 'ottimismo',
        'neutral': 'neutrale',
        'confusion': 'confusione',
        'caring': 'cura',
        'approval': 'approvazione',
        'disappointment': 'delusione',
        'sadness': 'tristezza',
        'love': 'amore',
        'admiration': 'ammirazione',
        'disapproval': 'disapprovazione',
        'excitement': 'eccitazione',
        'realization': 'realizzazione',
        'annoyance': 'fastidio',
        'surprise': 'sorpresa',
        'fear': 'paura',
        'remorse': 'rimorso',
        'nervousness': 'nervosismo',
        'joy': 'gioia',
        'anger': 'rabbia',
        'amusement': 'divertimento',
        'disgust': 'disgusto',
        'grief': 'lutto',
        'gratitude': 'gratitudine',
        'relief': 'rilievo',
        'embarrassment': 'imbarazzo',
        'pride': 'orgoglio'
    }

    # Controlla che l'output sia nel formato corretto
    if isinstance(output, list) and all(isinstance(item, dict) for item in output):
        for emozione in output:
            emozione['label'] = traduzione_label.get(emozione['label'], emozione['label'])  # Se il label non è nel dizionario, rimane invariato
    else:
        print("Attenzione: l'output non è nel formato previsto. Assicurati che sia una lista di dizionari.")

    return output

def process_text_with_models(text, model_1_pipeline, model_2_pipeline, model_1_id, model_2_id):
    """
    Esegue l'analisi di un messaggio usando due modelli, ricostruisce i risultati e li unisce.

    Args:
        text (str): Il messaggio da analizzare.
        model_1_pipeline: La pipeline del primo modello.
        model_2_pipeline: La pipeline del secondo modello.
        model_1_id (str): L'ID del primo modello.
        model_2_id (str): L'ID del secondo modello.
        reconstruct_word (function): Funzione per ricostruire parole complete dai sub-token.
        merge_results (function): Funzione per unire i risultati dei due modelli, dando preferenza al secondo modello.

    Returns:
        list: Lista di risultati finali dopo l'elaborazione e l'unione delle entità.
    """
    
    # 1. Esegui l'analisi solo se le pipeline sono caricate correttamente
    result_1 = []
    if model_1_pipeline:
        result_1 = model_1_pipeline(text)
    else:
        print(f"Errore nel caricare la pipeline per il modello 1: {model_1_id}")

    result_2 = []
    if model_2_pipeline:
        result_2 = model_2_pipeline(text)
    else:
        print(f"Errore nel caricare la pipeline per il modello 2: {model_2_id}")

    # 2. Ricostruisci i risultati dai sub-token in parole complete per entrambi i modelli
    reconstructed_model_1_results = reconstruct_word(result_1) if result_1 else []
    reconstructed_model_2_results = reconstruct_word(result_2) if result_2 else []

    # 3. Unisci i risultati dei due modelli, con la preferenza per il modello 2
    final_results = merge_results(reconstructed_model_1_results, reconstructed_model_2_results)

    return final_results
    

def process_emotions_and_translate(text, model_4_pipeline, model_3_pipeline):
    """
    Esegue la traduzione del testo, la classificazione delle emozioni nel testo tradotto
    e la traduzione dei label delle emozioni in italiano.

    Args:
        text (str): Il messaggio da elaborare.
        model_4_pipeline: La pipeline per la traduzione del testo.
        model_3_pipeline: La pipeline per la classificazione delle emozioni.
        traduci_output (function): Funzione per tradurre i label delle emozioni in italiano.

    Returns:
        list: Lista di emozioni con i label tradotti in italiano.
    """
    
    # 1. Tradurre il testo con il modello di traduzione
    text_tradotto = model_4_pipeline(text)
    
    # 2. Classificare le emozioni nel testo tradotto
    output_classificazione = model_3_pipeline(text_tradotto)
    
    # 3. Tradurre i label delle emozioni in italiano
    output_tradotto = [traduci_output(emozione) for emozione in output_classificazione]
    
    # 4. Restituire il risultato finale
    return output_tradotto