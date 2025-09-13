
# config.py
import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()


API_URL = "http://192.168.31.134:5001/api/chat"
API_IMAGINE = "http://192.168.31.134:5000/api/generate"
API_TIMEOUT = 190  # Timeout de 60 segundos

# Configurações do bot - com verificação
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("❌ Token do Discord não encontrado! Verifique o arquivo .env")

PREFIX = "!"

# Canais permitidos para comandos (substitua pelo ID real)
COMANDOS_CHANNEL_ID = 952739294294995054
CANAIS_PERMITIDOS = [COMANDOS_CHANNEL_ID]

# IDs de administradores
ADMIN_IDS = [284004335640379394]  # Substitua pelo seu ID do Discord

LOG_CHANNEL_ID = 952478390752018432  # ← COLOCAR O ID DO CANAL DE LOGS AQUI
if not LOG_CHANNEL_ID:
    raise ValueError("❌ ID do canal de logs não encontrado! Defina LOG_CHANNEL_ID em config.py")   