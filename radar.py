import os
import requests

print("1. Iniciando prueba...")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

url = f"https://telegram.org{TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "🚨 PRUEBA EXITOSA: Tu radar ya está conectado a Telegram"
}

resp = requests.post(url, data=payload)
print("2. Respuesta de Telegram:", resp.text)
