# data_semantics

# strutttura edel progetto

## utils.py
ci sono le varie funzioni che servono per glui scripts e notebook

## download.py
# fai girare solo la prima volta per scaricaere i modelli da hugging face
1. Importazione delle librerie e moduli
    ├── Importazione delle funzioni da `utils`
    ├── Importazione del modulo `os` per la gestione dei file di sistema
    ├── Importazione di `dotenv` per caricare il file `.env`

2. Caricamento delle variabili d'ambiente dal file `.env`
    └── Utilizzo di `load_dotenv` per caricare le variabili d'ambiente definite nel file `.env`

3. Recupero del token di autenticazione Hugging Face dal file `.env`
    └── Lettura della variabile `HUGGINGFACE_TOKEN` tramite `os.getenv()`

4. Definizione dei modelli e dei file da scaricare
    └── Creazione di un dizionario `models` con ID dei modelli e i relativi file da scaricare
    └── Lettura delle variabili `MODEL_1_ID`, `MODEL_2_ID`, `MODEL_1_FILES` e `MODEL_2_FILES` dal file `.env`
    └── Separazione dei nomi dei file tramite `split(",")` per ogni modello

5. Funzione principale di esecuzione
    └── Ciclo che scarica i file per ogni modello definito nel dizionario `models`
    └── Stampa il messaggio di avvio del download per ogni modello
    └── Chiamata alla funzione `download_model_files` per scaricare i file specificati

## ner_combination.ipynb
il notebook è parlate e molto breve, vedi quello