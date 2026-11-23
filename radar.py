import os
import re
import json
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ARCHIVO_HISTORIAL = "historial.json"
URL_TIENDA = "https://toscrape.com"

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=2)

def enviar_telegram(mensaje):
    url = f"https://telegram.org{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def escanear():
    historial = cargar_historial()
    respuesta = requests.get(URL_TIENDA)
    soup = BeautifulSoup(respuesta.text, "html.parser")

    for item in soup.select(".product_pod"):
        titulo = item.h3.a["title"]
        enlace = "https://toscrape.com" + item.h3.a["href"]
        
        # Extrae solo los números y el punto decimal (evita fallos con símbolos de moneda)
        precio_texto = item.select_one(".price_color").text
        precio = float(re.sub(r"[^\d.]", "", precio_texto))

        # En esta web de prueba el libro más barato cuesta 13.99, así que avisará con < 15.0
        if precio < 15.0 and enlace not in historial:
            msg = f"🚨 <b>CHOLLO DETECTADO</b>\n📦 {titulo}\n💰 Precio: <b>{precio}</b>\n🔗 <a href='{enlace}'>Ver producto</a>"
            enviar_telegram(msg)
            historial.append(enlace)

    # Guarda siempre el archivo para evitar el error en GitHub Actions
    guardar_historial(historial)

if __name__ == "__main__":
    escanear()
