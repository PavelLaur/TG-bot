import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY')
