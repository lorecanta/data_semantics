# Analisi Semantica Forum

## Descrizione del Progetto
Questo progetto ha lo scopo di estrarre, analizzare e visualizzare dati semantici dal forum PMA https://quelledialfpma.forumfree.it/, utilizzando modelli NLP. I dati vengono salvati in un database MongoDB e possono essere analizzati attraverso report HTML o query manuali.

## Struttura della Cartella

### Notebook Principali
1. **main_data_storage.ipynb**
   - Estrazione dei dati dal forum.
   - Integrazione dei dati con i risultati delle analisi semantiche.
   - Salvataggio su MongoDB.
   - Possibilità di selezionare discussioni specifiche e intervalli di date.

2. **main_analysis_report.ipynb**
   - Creazione di un report sulle emozioni.
   - Filtraggio per una specifica tipologia di entità del NER.
   - Output: un file HTML contenente il report.

3. **main_analysis_manual_query.ipynb**
   - Analisi manuale tramite query personalizzate.
   - Possibilità di esaminare la distribuzione delle emozioni su una discussione senza filtrare con i risultati NER.

### Cartelle e File Aggiuntivi
- **shared/**: Contiene vari file di utils per supportare i processi di estrazione, analisi e salvataggio dei dati.
- **download.py**: Script per scaricare in locale i modelli semantici da Hugging Face.

## Requisiti
- Assicurati di avere installati i seguenti pacchetti:
```bash
pip install -r requirements.txt
```
- avere installato MongoDBCompass

## Utilizzo

1. **Scaricare i modelli NLP**
   ```bash
   python download.py
   ```

2. **Eseguire il notebook di estrazione dati** (`main_data_storage.ipynb`).

3. **Generare un report automatico** con `main_analysis_report.ipynb`.

4. **Eseguire query manuali** con `main_analysis_manual_query.ipynb` per analisi personalizzate.

## Note
- I dati sono salvati su MongoDB, quindi assicurati che il server Mongo sia attivo.
- Il progetto utilizza modelli di Hugging Face, che devono essere scaricati prima di eseguire le analisi.


