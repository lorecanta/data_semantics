from pymongo import MongoClient
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from collections import Counter
import base64
import io 

def calculate_statistics(emotions_scores):
    stats = []
    for emotion, scores in emotions_scores.items():
        scores_array = np.array(scores)
        stats.append([
            emotion,
            np.min(scores_array),
            np.max(scores_array),
            np.mean(scores_array),
            np.median(scores_array),
            np.var(scores_array),
            pd.Series(scores_array).skew()
        ])
    df = pd.DataFrame(stats, columns=["Emozione", "Min", "Max", "Media", "Mediana", "Varianza", "Asimmetria"])
    return df


def plot_emotion_means(emotion_dict, plot_type='bar', save_path='plots/'):
    # Create the directory if it doesn't exist
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    
    # Define colors for the emotions
    emotion_colors = {
        "gioia": "green", "ottimismo": "limegreen", "gratitudine": "lightgreen",
        "amore": "mediumseagreen", "curiosità": "yellowgreen",
        "tristezza": "red", "paura": "darkred", "rabbia": "crimson",
        "delusione": "orangered", "nervosismo": "tomato", "fastidio": "brown",
        "disgusto": "purple", "divertimento": "pink", "imbarazzo": "lightcoral",
        "neutrale": "gray", "confusione": "slategray", "realizzazione": "teal",
        "approvazione": "blue", "lutto": "black", "desiderio": "violet",
        "cura": "turquoise", "rilievo": "lightblue", "ammirazione": "gold",
        "rimorso": "indianred", "eccitazione": "orange", "sorpresa": "fuchsia",
        "orgoglio": "navy", "disapprovazione": "darkslategray"
    }

    # Calculate the mean for each emotion
    emotions = list(emotion_dict.keys())
    means = [np.mean(emotion_dict[emotion]) for emotion in emotions]

    # Handle emotions not in the color dictionary
    def get_color(emotion):
        return emotion_colors.get(emotion, "gray")  # Default color for unknown emotions

    colors = [get_color(emotion) for emotion in emotions]

    fig = None  # Initialize figure

    if plot_type == 'bar':
        # Bar plot
        fig = plt.figure(figsize=(12, 14))
        plt.bar(emotions, means, color=colors)
        plt.xlabel("Emozioni")
        plt.ylabel("Media del punteggio")
        plt.title("Media dei punteggi per ogni emozione")
        plt.xticks(rotation=90)

    elif plot_type == 'boxplot':
        # Convert dictionary to long format suitable for Seaborn
        data = []
        for emotion, values in emotion_dict.items():
            for value in values:
                data.append({'Emozione': emotion, 'Punteggio': value})
        # Create DataFrame
        df = pd.DataFrame(data)
        
        fig = plt.figure(figsize=(12, 14))
        sns.boxplot(x='Emozione', y='Punteggio', data=df, palette=emotion_colors)
        plt.xlabel("Emozioni")
        plt.ylabel("Punteggio")
        plt.title("Boxplot dei punteggi per ogni emozione")
        plt.xticks(rotation=90)

    elif plot_type == 'kde':
        # Create a density plot for each emotion (relative density)
        num_emotions = len(emotions)
        ncols = 4  # Adjust if necessary
        nrows = (num_emotions // ncols) + (num_emotions % ncols > 0)

        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(20, 6 * nrows), sharey=True)
        axes = axes.flatten()

        for i, (ax, emotion) in enumerate(zip(axes, emotions)):
            sns.kdeplot(emotion_dict[emotion], ax=ax, label=emotion, color=get_color(emotion), common_norm=True)
            ax.set_title(emotion)
            ax.set_xlabel("Punteggio")
            ax.set_ylabel("Densità")
            ax.legend(title='Emozione')
        
        # Hide unused subplots
        for j in range(i + 1, len(axes)):
            axes[j].axis('off')

        plt.tight_layout()

    elif plot_type == "correlation":
        # Convert the dictionary to a DataFrame for analysis
        df = pd.DataFrame(emotion_dict)
        correlation_matrix = df.corr()
        fig = plt.figure(figsize=(17, 15))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt='.2f', linewidths=0.5)
        plt.title("Matrice di Correlazione tra Emozioni")

    else:
        print("Tipo di grafico non riconosciuto. Usa 'bar', 'boxplot', 'kde' o 'correlation'.")

    # Return the figure
    return fig



def get_top_entities(entity, n, db_name):
    """
    Estrae le 'n' parole più frequenti associate a una determinata entità in un database MongoDB.

    :param entity: Il tipo di entità da analizzare (es. "PER", "LOC").
    :param n: Numero di parole più frequenti da restituire.
    :param db_name: Nome del database MongoDB (default: "analisi_centri").
    :return: Lista delle 'n' parole più frequenti associate all'entità.
    """
    # Connetti al database MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client[db_name]
    collection = db["post"]

    # Query per filtrare i documenti contenenti l'entità
    query = {"ner.entity": entity}
    documents = collection.find(query)

    # Contatore per le entità
    entity_counter = Counter()

    # Conta la frequenza delle parole associate all'entità
    for doc in documents:
        for item in doc.get("ner", []):
            if item.get("entity") == entity:
                entity_counter[item.get("word")] += 1

    # Seleziona le 'n' parole più frequenti
    return [word for word, _ in entity_counter.most_common(n)]


def generate_entity_section(index, entity, emotion_scores):
    # Crea la sezione per ogni entità
    plot_files = []
    plot_types = ["bar", "boxplot", "kde", "correlation"]
    
    # Creazione dei grafici e memorizzazione come base64 (in memoria)
    for plot_type in plot_types:
        fig = plot_emotion_means(emotion_scores, plot_type=plot_type)
        
        # Cattura l'immagine del grafico in un buffer
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png')
        img_buffer.seek(0)

        # Codifica l'immagine in base64
        img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
        plot_files.append(f"data:image/png;base64,{img_base64}")
        plt.close(fig)  # Chiudi la figura per liberare memoria
    
    # Calcola la tabella delle statistiche (assumendo che sia un DataFrame)
    table_statistics = calculate_statistics(emotion_scores)
    table_html = table_statistics.to_html()

    # Restituisce una sezione HTML per questa entità
    return f"""
    <div class="section" id="section_{index}">
        <h2>{entity}</h2>

        <!-- Entity Description Section -->
        <div class="section">
            <h3>Statistics Table</h3>
            <div class="table-container">
                {table_html}
            </div>
        </div>

        <!-- Emotion Analysis Plots Section -->
        <div class="section">
            <h3>Emotion Analysis Plots</h3>
            <p>Below are the emotion analysis plots for <strong>{entity}</strong>:</p>

            <div>
                <h4>Bar Plot</h4>
                <img src="{plot_files[0]}" alt="Bar Plot" class="plot-image">
            </div>

            <div>
                <h4>Boxplot</h4>
                <img src="{plot_files[1]}" alt="Boxplot" class="plot-image">
            </div>

            <div>
                <h4>KDE Plot</h4>
                <img src="{plot_files[2]}" alt="KDE Plots" class="plot-image">
            </div>

            <div>
                <h4>Correlation Plot</h4>
                <img src="{plot_files[3]}" alt="Correlation Plot" class="plot-image">
            </div>
        </div>
    </div>
    """

def generate_combined_emotion_analysis_report(title, db_name, entity, top_entities):
    # Inizializza un dizionario per raccogliere tutte le informazioni delle emozioni per ciascuna entità
    client = MongoClient("mongodb://localhost:27017/")
    db = client[db_name]
    collection = db["post"]

    all_emotion_scores = {}

    # Crea un dizionario per memorizzare tutte le informazioni per ogni top entity
    for i in range(0, 5):
        entity = entity
        query = {
            "ner": {
                "$elemMatch": {
                    "entity": entity,  # Filtro per entità
                    "word": top_entities[i]  # Filtro per parola
                }
            }
        }

        # Recupera i documenti filtrati
        documents = collection.find(query)

        # Inizializza un dizionario con liste vuote per ogni emozione per questa entità
        emotion_scores = {}

        # Itera sui documenti filtrati
        for doc in documents:
            sentiment_analysis = doc.get("sentiment_analysis_full", {})

            for emotion, score in sentiment_analysis.items():
                if emotion not in emotion_scores:
                    emotion_scores[emotion] = []  # Crea la lista se non esiste
                emotion_scores[emotion].append(score)  # Aggiunge lo score
        
        # Salva i punteggi emozionali per questa entità
        all_emotion_scores[top_entities[i]] = emotion_scores
    
    # Crea un unico report HTML con il nuovo design
    report_html = f"""
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #fafafa;
                color: #333;
                line-height: 1.6;
            }}
            h1 {{
                text-align: center;
                color: #34495e;
                font-size: 40px;
                margin-bottom: 20px;
            }}
            h2 {{
                color: #2c3e50;
                font-size: 32px;
                margin-top: 30px;
                margin-bottom: 10px;
            }}
            h3 {{
                color: #7f8c8d;
                font-size: 26px;
                margin-bottom: 10px;
            }}
            .section {{
                margin-bottom: 40px;
                padding: 20px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .table-container {{
                margin-top: 20px;
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border: 1px solid #ddd;
                font-size: 16px;
            }}
            th {{
                background-color: #ecf0f1;
                color: #34495e;
                font-weight: bold;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            tr:hover {{
                background-color: #f1f1f1;
            }}
            .plot-image {{
                max-width: 100%;
                margin: 30px 0;  /* Maggiore distanza tra i grafici */
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .index {{
                margin-bottom: 20px;
                padding: 10px;
                background-color: #2c3e50;
                color: #fff;
                border-radius: 8px;
                text-align: center;
            }}
            .index a {{
                color: #fff;
                text-decoration: none;
                margin: 0 15px;
                font-size: 18px;
                padding: 5px 10px;
                border-radius: 5px;
                background-color: #34495e;
            }}
            .index a:hover {{
                background-color: #2980b9;
            }}
            .index a:active {{
                background-color: #1abc9c;
            }}
        </style>
    </head>
    <body>

        <h1>{title}</h1>

        <!-- Index with clickable links -->
        <div class="index">
            {''.join([f'<a href="#section_{i}">{top_entities[i]}</a>' for i in range(5)])}
        </div>

        <!-- Dynamically generating sections for each entity -->
        {''.join([generate_entity_section(i, top_entities[i], all_emotion_scores[top_entities[i]]) for i in range(5)])}

    </body>
    </html>
    """

    # Salva il report HTML in un file
    with open(f"{title}_emotion_analysis_report.html", "w") as file:
        file.write(report_html)

    print(f"HTML report has been generated and saved as '{title}_emotion_analysis_report.html'.")

from pymongo import MongoClient

def get_emotion_scores(query):
    client = MongoClient("mongodb://localhost:27017/")  # Assicurati che l'URL sia corretto
    db = client["analisi_centri"]  # Nome del database
    collection = db["post"]  # Nome della collezione

    # Recupera i documenti filtrati
    documents = collection.find(query)

    # Inizializza un dizionario con liste vuote per ogni emozione
    emotion_scores = {}

    # Itera sui documenti filtrati
    for doc in documents:
        sentiment_analysis = doc.get("sentiment_analysis_full", {})

        for emotion, score in sentiment_analysis.items():
            if emotion not in emotion_scores:
                emotion_scores[emotion] = []  # Crea la lista se non esiste
            emotion_scores[emotion].append(score)  # Aggiunge lo score

    return emotion_scores