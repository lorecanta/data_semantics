import datetime

import requests
from bs4 import BeautifulSoup
import re
import logging
from emoji import demojize
import emoji
from pymongo import MongoClient
from urllib.parse import urlparse, urlunparse
import pickle


LOGGER = logging.getLogger("scraper")


BASE_URL = "https://quelledialfpma.forumfree.it/"
QUOTE_PATTERN = re.compile(r'(.*)\((.*) @ (\d{1,2}\/\d{1,2}\/\d{4}), (\d{2}:\d{2})\).*href="([^"]+)')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

# MongoDB Connection Details (replace placeholders)
MONGODB_URI = "mongodb://localhost:27017?retryWrites=true&w=majority"


def save_data_locally(data, base_filename):
    try:
        # Ottieni la data e l'ora attuali nel formato desiderato (YYYY-MM-DD_HH-MM-SS)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Crea il nome del file con il suffisso "_data_odiena"
        filename = f"{base_filename}_{current_time}.pkl"

        # Salva i dati nel file
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
        logging.info(f"Dati salvati correttamente in {filename}")
    except Exception as e:
        logging.error(f"Si è verificato un errore durante il salvataggio dei dati: {e}")


def extract_emoji_positions(text):
    emojis_with_positions = []
    for pos, char in enumerate(text):
        if char in emoji.EMOJI_DATA:
            emojis_with_positions.append({'emoji': char, 'pos': pos})
    return emojis_with_positions

def normalize_url(url):
    """Normalizza l'URL rimuovendo differenze come / e //."""
    parsed = urlparse(url)
    normalized_path = parsed.path.replace("//", "/")
    return urlunparse(parsed._replace(path=normalized_path))

def remove_after_pm_email(text):
    keyword = "PM Email"
    idx = text.find(keyword)
    if idx != -1:
        text = text[:idx].strip()
    return text


def extract_post(post):
    """
    Extract a post as dictionary from a post div available in a discussion.
    :param post: div of the post in HTML
    :return:
    """
    try:
        # Estrazione dell'autore
        author_element = post.find('div', class_='nick')
        author = author_element.a.text.strip() if author_element and author_element.a else 'Unknown'

        # Estrazione della data e ora
        timestamp_element = post.find('span', class_='when')
        if timestamp_element and timestamp_element.text:
            timestamp_text = timestamp_element.text.strip()
            date_time = timestamp_text.split('Posted on')[-1].strip()
            date, time = date_time.split(', ') if ', ' in date_time else (None, None)
        else:
            date, time = None, None

        # Estrazione del messaggio
        message_element = post.find('td', class_='right Item')
        if message_element:
            message = message_element.get_text(separator=' ', strip=True)
        else:
            message = None

        message = remove_after_pm_email(message)
        message_emojis = extract_emoji_positions(message)
        message_cleaned = demojize(message).strip().rstrip('.')

        # Estrazione delle citazioni
        quotes = []
        quote_tags = post.find_all('div', class_='quote_top')
        for quote_tag in quote_tags:
            quote_html = str(quote_tag)
            quote_match = QUOTE_PATTERN.search(quote_html)
            if quote_match:
                quote_author = quote_match.group(2)
                quote_date = quote_match.group(3)
                quote_time = quote_match.group(4)
                quote_href = quote_match.group(5)

                quote_content_tag = quote_tag.find_next_sibling('div', class_='quote')
                if quote_content_tag:
                    quote_content = quote_content_tag.get_text(separator=' ', strip=True)
                    quote_emojis = extract_emoji_positions(quote_content)
                    quote_cleaned = demojize(quote_content).strip()

                    quote_dict = {
                        'quote_author': quote_author,
                        'quote_date': quote_date,
                        'quote_time': quote_time,
                        'quote_href': quote_href,
                        'quote_content': quote_cleaned
                    }

                    if quote_emojis:
                        quote_dict['quote_emojis'] = quote_emojis

                    quotes.append(quote_dict)

                    # Rimuovi il contenuto della citazione dal messaggio principale
                    if quote_content:
                        message_cleaned = message_cleaned.replace(quote_cleaned, '').strip()

        # Creazione del dizionario finale
        post_dict = {
            'author': author,
            'date': date,
            'time': time,
            'message': message_cleaned,
        }

        if message_emojis:
            post_dict['message_emojis'] = message_emojis

        if quotes:
            post_dict['quotes'] = quotes

        return post_dict

    except AttributeError as e:
        logging.warning(f"Errore di attributo: {e}. \nPost: {post}")
    except Exception as e:
        logging.warning(f"Errore sconosciuto: {e}. \nPost: {post}")

    return None


def extract_discussion_title(url):
    """
    This function extract the discussions title from the URL of the discussion.
    :param url: URL to the forum discussion.
    :return:
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading page {url}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    discussion_text = soup.find('body').find("table").find("h1").text.strip()
    return discussion_text


def extract_posts(url: str, start_date: datetime, end_date: datetime):
    """
    Given a URL to a discussion this function extracts all the posts for that discussion.
    The function can deal with pagination, iterating pages until at least one post is returned.
    :param url: URL to the forum discussion
    :param start_date: Start date to filter posts
    :param end_date: End date to filter posts
    :return: A list of posts filtered by date
    """
    posts = []
    page = 0
    while True:
        paginated_url = f"{url}&st={page * 15}"
        try:
            response = requests.get(paginated_url, headers=HEADERS, timeout=10)  # Add timeout for robustness
            response.raise_for_status()  # Raise exception for bad responses
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading page {url}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        post_divs = soup.find_all('li', class_='post')

        if not post_divs:
            logging.warning(f"No posts found on page {url}")

        paginated_posts = []

        for post in post_divs:
            post_dict = extract_post(post=post)
            if post_dict and "date" in post_dict:
                try:
                    # Converte la data del post in un oggetto datetime
                    post_date = datetime.datetime.strptime(post_dict["date"], "%d/%m/%Y")
                    # Controlla se la data del post è tra start_date e end_date
                    if start_date <= post_date <= end_date:
                        paginated_posts.append(post_dict)
                except ValueError:
                    logging.warning(f"Invalid date format for post: {post_dict['date']}")
                    continue  # Ignora i post con data non valida

        # Aggiungi i post filtrati alla lista finale
        if paginated_posts:
            posts.extend(paginated_posts)

        # Se non ci sono più post da paginare, interrompi
        if len(post_divs) < 15:  # Se il numero di post sulla pagina è inferiore a 15, probabilmente siamo all'ultima pagina
            break

        page += 1

    return posts


def download_and_parse(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)  # Timeout added for robustness
        response.raise_for_status()  # Raise exception for bad responses
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading page {url}: {str(e)}")
        return None


def extract_sections(soup):
    sections = []

    section_elements = soup.find_all('li', {'class': 'off'})

    class_to_type = {
        'web': 'Section',
        'mobile': 'Mobile',
        'altro': 'Other'
    }

    for section in section_elements:
        try:
            # Check if the element is a section and not an ad or discussion
            if 'aa' in section.div['class']:
                section_title = section.find('h3', {'class': 'web'}).text.strip()
                section_description = section.find('h4', {'class': 'desc'}).text.strip() if section.find('h4', {'class': 'desc'}) else ""
                topics_count = section.find('div', {'class': 'topics'}).em.text.strip() if section.find('div', {'class': 'topics'}) else "N/A"
                replies_count = section.find('div', {'class': 'replies'}).em.text.strip() if section.find('div', {'class': 'replies'}) else "N/A"

                last_post_info_tag = section.find('div', {'class': 'zz'}).find('div', {'class': 'when'})
                if last_post_info_tag:
                    last_post_info = last_post_info_tag.text.strip()
                    last_post_date, last_post_time = last_post_info.split(', ')
                else:
                    last_post_date = "N/A"
                    last_post_time = "N/A"

                section_class = section.find('h3').get('class', [''])[0]
                section_type = class_to_type.get(section_class, 'N/A')

                link = section.find('h3', {'class': 'web'}).a['href']
                if not link.startswith(BASE_URL):
                    link = BASE_URL + link

                section_id = re.search(r'\?(.?)=(\d+)', link).group(2)
                is_private = 'res' in section['class'] or 'password' in section_description.lower()

                sections.append({
                    "ID": section_id,
                    "Title": section_title,
                    "Description": section_description,
                    "Number of Discussions": topics_count,
                    "Number of Replies": replies_count,
                    "Last Message Date": last_post_date,
                    "Last Message Time": last_post_time,
                    "Link": link,
                    "Is Private": is_private
                })
        except AttributeError as e:
            logging.warning(f"Error extracting data from section: {str(e)}")

    return sections

def extract_sections_paginated(url):
    """Estrae le sezioni iterando su eventuali pagine, con gestione speciale per BASE_URL."""
    sections = []
    normalized_base_url = normalize_url(BASE_URL)
    normalized_url = normalize_url(url)  # Normalizza l'URL in ingresso

    if normalized_url == normalized_base_url:
        # Gestione speciale per BASE_URL: una sola estrazione
        logging.info(f"Extracting sections from BASE_URL: {url}")
        soup = download_and_parse(url)
        if soup:
            sections = extract_sections(soup)
    else:
        # Estrazione iterativa per URL generici
        page = 0
        while True:
            download_url = normalized_url if page == 0 else f"{normalized_url}&st={page * 30}"
            logging.info(f"Downloading sections from: {download_url}")  # Log the URL being downloaded

                        # Controlla se siamo all'ultima pagina a partire dalla seconda
            if page > 0:
                current_url = normalize_url(soup.find('link', rel='canonical')['href'])
                if current_url != normalize_url(download_url):
                    break

            soup = download_and_parse(download_url)
            if soup:
                page_sections = extract_sections(soup)
                sections.extend(page_sections)

            page += 1

    # Filtro per rimuovere le sezioni con 'Number of Discussions': 'N/A'
    filtered_sections = [
        section for section in sections
        if section.get('Number of Discussions') != 'N/A'
    ]

    return filtered_sections


def extract_all_sections_recursive(url, all_sections=None):
    """Esplora ricorsivamente tutte le sezioni a partire da un URL e raccoglie tutte le sezioni in un'unica lista."""
    if all_sections is None:
        all_sections = []  # Inizializza la lista di sezioni se non è stata passata

    # Estrai le sezioni dalla pagina corrente
    soup = download_and_parse(url)
    if soup:
        sections = extract_sections(soup)

        # Filtro per rimuovere le sezioni con 'Number of Discussions': 'N/A'
        sections = [
            section for section in sections
            if section.get('Number of Discussions') != 'N/A'
        ]
        
        all_sections.extend(sections)  # Aggiungi le sezioni alla lista principale

        # Esplora i link alle sezioni figlie (se esistono)
        for section in sections:
            link = section.get("Link")
            if link:  # Se il link esiste, esplora quella sezione
                logging.info(f"Exploring link: {link}")
                extract_all_sections_recursive(link, all_sections)

    return all_sections

def extract_discussions(soup):
    data = []
    if soup:
        items = soup.select("ol.big_list > li")

        for item in items:
            try:
                title = item.select_one("div.bb h3.web a").text
                link = BASE_URL + item.select_one("div.bb h3.web a")['href']
                author = item.select_one("div.xx a").text
                replies = item.select_one("div.yy div.replies em").text
                views = item.select_one("div.yy div.views em").text

                item_type = "announcement" if 'annuncio' in item['class'] else "discussion"

                data.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "replies": replies,
                    "views": views,
                    "type": item_type
                })
            except AttributeError as e:
                logging.warning(f"Error extracting data from discussion/announcement: {str(e)}")
    return data


def extract_discussions_paginated(url):
    """Estrae le discussioni iterando su eventuali pagine."""
    discussions = []
    page = 0
    original_url = normalize_url(url)  # Normalizza l'URL originale

    while True:
        download_url = original_url if page == 0 else f"{original_url}&st={page * 30}"
        logging.info(f"Downloading discussions from: {download_url}")  # Log the URL being downloaded

        soup = download_and_parse(download_url)
        if not soup:
            logging.warning(f"Failed to download or parse the page: {download_url}")
            break  # Se non riesce a scaricare o analizzare la pagina, interrompe il ciclo

        # Starting from the second page, check if it's the last page
        if page > 0:
            canonical_link = soup.find('link', rel='canonical')
            if not canonical_link or 'href' not in canonical_link.attrs:
                logging.warning(f"Canonical link not found or invalid on page: {download_url}")
                break  # Interrompe se non riesce a trovare il link canonico
            current_url = normalize_url(canonical_link['href'])
            if current_url != normalize_url(download_url):
                break

        # Estrai le discussioni dalla pagina
        page_discussions = extract_discussions(soup)
        discussions.extend(page_discussions)

        page += 1

    return discussions


def estrai_autori(lista_dizionari, autori_accumulati):
    """
    Estrae i valori unici di 'author' da una lista di dizionari,
    elimina 'Unknown' e aggiorna il set degli autori accumulati.
    """
    # Aggiorna il set con i nuovi autori (escludendo 'Unknown')
    autori_accumulati.update({d["author"].lower() for d in lista_dizionari if d["author"].lower() != "unknown"})


def process_discussions(items):
    """
    Processa una lista di elementi, stampa informazioni sulle discussioni
    e restituisce un'unica lista con tutte le discussioni estratte.

    Args:
        items (list): Lista di dizionari con le informazioni sugli elementi.

    Returns:
        list: Lista totale di tutte le discussioni estratte.
    """
    discussioni_totali = []

    for item in items:
        # Estrazione delle informazioni dall'elemento
        title = item.get("Title")
        num_discussions = item.get("Number of Discussions")
        link = item.get("Link")

        # Log delle informazioni sull'elemento corrente
        logging.info(f"Titolo: {title}")
        logging.info(f"Numero di discussioni dichiarato: {num_discussions}")

        try:
            # Estrazione delle discussioni usando la funzione fornita
            discussioni = extract_discussions_paginated(link)

            # Aggiunta delle informazioni della sezione a ogni discussione
            for discussione in discussioni:
                discussione["title_section"] = title
                discussione["link_section"] = link

            logging.info(f"Numero di discussioni estratte: {len(discussioni)}")
        except Exception as e:
            # Log dell'errore se qualcosa va storto
            logging.error(f"Errore nell'estrazione delle discussioni per il link {link}: {e}")
            discussioni = []

        # Log separatore tra ogni discussione
        logging.info("------------------------------------")

        # Aggiunta delle discussioni alla lista totale
        discussioni_totali.extend(discussioni)

     # Rimozione dei duplicati basata sulle chiavi specificate
    discussioni_uniche = []
    viste = set()

    for discussione in discussioni_totali:
        # Crea una tupla con i valori delle chiavi selezionate
        chiavi_valori = tuple(discussione.get(chiave) for chiave in ["title","author","replies"])

        if chiavi_valori not in viste:
            viste.add(chiavi_valori)
            discussioni_uniche.append(discussione)

    return discussioni_totali

def process_forum_data(url="https://quelledialfpma.forumfree.it/", save_to_local=False):
    try:
        # Log dell'inizio del processo
        logging.info(f"Inizio elaborazione dell'URL: {url}")

        # Estrarre tutte le sezioni ricorsivamente
        logging.info("Estrazione delle sezioni in corso...")
        sections = extract_all_sections_recursive(url)
        logging.info(f"Estrazione completata. Numero di sezioni trovate: {len(sections) if sections else 0}")

        # Processare le discussioni
        logging.info("Elaborazione delle discussioni in corso...")
        discussions = process_discussions(sections)
        logging.info(f"Elaborazione completata. Numero di discussioni processate: {len(discussions) if discussions else 0}")

        # Salvataggio dei dati in locale solo se il parametro è True
        if save_to_local:
            logging.info("Salvataggio dei dati in locale...")
            save_data_locally(sections, "sections")
            save_data_locally(discussions, "discussions")
            logging.info("Dati salvati con successo.")

        # Ritorno dei risultati
        return sections, discussions

    except Exception as e:
        logging.error(f"Si è verificato un errore durante l'elaborazione: {e}")
        return None
    

def insert_post_to_mongo(post_dict, database_name, collection_name, chiavi_deduplicazione):
    """
    Inserisce un dizionario nella collezione MongoDB specificata se non esiste già.

    Parameters:
    - post_dict: Dizionario contenente i dati del post da inserire.
    - database_name: Nome del database MongoDB.
    - collection_name: Nome della collezione in cui inserire il post.
    - chiavi_deduplicazione: Lista di chiavi da utilizzare per verificare la presenza di duplicati.
    """
    # Configurazione della connessione a MongoDB
    client = MongoClient(MONGODB_URI)
    db = client[database_name]
    collection = db[collection_name]

    # Creazione del filtro di deduplicazione basato sulle chiavi specificate
    filtro = {chiave: post_dict.get(chiave) for chiave in chiavi_deduplicazione}

    # Controllo se il documento esiste già
    existing_post = collection.find_one(filtro)

    if existing_post:
        print(f"Post con {filtro} già esistente. Salto l'inserimento.")
    else:
        collection.insert_one(post_dict)
        print(f"Post con {filtro} inserito nella collezione.")


def process_posts(discussioni, database_name, start_date=None, end_date=None):
    """
    Processes the posts between the specified start and end dates, 
    and inserts them into MongoDB. Defaults to 01/01/2001 for start_date
    and 12/31/2070 for end_date if not provided.

    Parameters:
    - start_date: The start date (datetime) for filtering posts (optional).
    - end_date: The end date (datetime) for filtering posts (optional).
    """
    # Default date values if not provided
    if start_date is None:
        start_date = datetime.datetime(2001, 1, 1)
    else:
        # Converti la stringa in datetime se è passata come stringa
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    if end_date is None:
        end_date = datetime.datetime(2070, 12, 31)
    else:
        # Converti la stringa in datetime se è passata come stringa
        if isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")

    autori_unici = set()

    # Iterate through results and extract posts
    for i in discussioni:
        posts = extract_posts(i["link"], start_date, end_date)
        discussion_title = i["title"]
        discussion_link = i["link"]
        discussion_author = i["author"]
        section_link = i["link_section"]
        section_title = i["title_section"]
        
        for j in posts:
            # Create a dictionary with the post and discussion data
            post_dict = {
                "section_title": section_title,
                "section_link": section_link,
                "discussion_title": discussion_title,
                "discussion_link": discussion_link,
                "discussion_author": discussion_author,
                **j  # Flatten the post data directly into the dictionary
            }

            print(post_dict)

            if "author" in j:
                autore = j["author"].lower()  # Autore in minuscolo per evitare duplicati
                autori_unici.add(autore)

            # Insert the post_dict into MongoDB
            insert_post_to_mongo(post_dict, database_name, "post", ["message","author"])

    for autore in autori_unici:
        autore_dict = {"author":autore}

        insert_post_to_mongo(autore_dict,database_name,"autori",["author"])




def process_forum_data_and_insert(database_name, start_date, end_date, url="https://quelledialfpma.forumfree.it/"):
    # Estrazione dei dati dal forum
    result_sections, result_discussion = process_forum_data(url)
    
    # Inserimento delle sezioni nel database (iterando su ogni sezione)
    for sezione in result_sections:
        insert_post_to_mongo(sezione, database_name, "sezioni", ["ID"])
    
    # Inserimento delle discussioni nel database (iterando su ogni discussione)
    for discussione in result_discussion:
        insert_post_to_mongo(discussione, database_name, "discussioni", ["title", "replies", "author"])
    
    # Elaborazione dei post nel database
    process_posts(result_discussion, database_name, start_date, end_date)


def filtra_discussioni(result_discussion, nomi_da_cercare):
    return [d for d in result_discussion if d.get("title") in nomi_da_cercare]


def data_storage(database_name, disc_da_cercare, start_date=None, end_date= None):
    result_sections, result_discussion = process_forum_data()
    result_discussion_subset = filtra_discussioni(result_discussion, disc_da_cercare)
    
    for sezione in result_sections:
        insert_post_to_mongo(sezione, database_name, "sezioni", ["ID"])
    for discussione in result_discussion:
        insert_post_to_mongo(discussione, database_name, "discussioni", ["title", "replies", "author"])
    
    process_posts(result_discussion_subset, database_name, start_date, end_date)
    print("Processo forum completato!")
