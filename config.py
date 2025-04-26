import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Session Telegram
    SESSION_NAME = os.getenv("SESSION_NAME", "torrent_bot")

    # API Telegram
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "")

    # Liste des administrateurs
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip().isdigit()]


    # Mode webhook (True/False)
    WEBHOOK = os.getenv("WEBHOOK", "False").lower() == "true"


config = Config()