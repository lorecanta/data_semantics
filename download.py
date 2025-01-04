from utils import download_model_files
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
from dotenv import load_dotenv
load_dotenv()

# Ottieni il token dal file .env
token = os.getenv("HUGGINGFACE_TOKEN")

# Modelli e relativi file da scaricare, presi dal file .env
models = {
    os.getenv("MODEL_1_ID"): os.getenv("MODEL_1_FILES").split(","),
    os.getenv("MODEL_2_ID"): os.getenv("MODEL_2_FILES").split(",")
}

# Scarica i file per ogni modello
if __name__ == "__main__":
    for model_id, file_names in models.items():
        print(f"Downloading files for model: {model_id}")
        download_model_files(model_id, file_names, token)