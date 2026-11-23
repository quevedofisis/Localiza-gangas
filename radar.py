import os
import re
import json
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ARCHIVO_HISTORIAL = "historial.json"

# Canal oficial RSS de los últimos chollos publicados en Chollometro
URL_RSS = "https://chollometro.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_historial(historial):
    # Guardamos solo los últimos 300 enlaces para que el archivo no crezca infinito
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial[-300:], f, indent=2)

def enviar_telegram(mensaje):
    servidor = "https://api." + "telegram.org"
    url = f"{servidor}/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    requests.post(url, data=payload)

def analizar_chollo(titulo, descripcion_html):
    texto_limpio = BeautifulSoup(descripcion_html, "html.parser").get_text(" ")
    todo_el_texto = f"{titulo} {texto_limpio}".lower()

    # 1. Buscar palabras clave de error de precio o gratis
    palabras_clave = ["error de precio", "0€", "0 €", "0,00€", "0,00 €", "gratis", "100% dto", "100% de descuento"]
    for palabra in palabras_clave:
        if palabra in todo_el_texto:
            return True, f"Palabra clave detectada: '{palabra}'"

    # 2. Buscar porcentajes de descuento del 80% al 99%
    descuentos = re.findall(r"(\d{2,3})\s*%", todo_el_texto)
    for d in descuentos:
        if 80 <= int(d) <= 100:
            return True, f"Descuento extremo: {d}%"

    return False, ""

def escanear():
    historial = cargar_historial()
    respuesta = requests.get(URL_RSS, headers=HEADERS, timeout=20)
    
    if respuesta.status_code != 200:
        print("Error al conectar con Chollometro:", respuesta.status_code)
        return

    raiz = ET.fromstring(respuesta.content)
    items = raiz.findall(".//item")
    print(f"Analizando {len(items)} chollos recientes...")

    for item in items:
        titulo = item.find("title").text or "Sin título"
        enlace = item.find("link").text or ""
        descripcion = item.find("description").text or ""

        if enlace in historial:
            continue

        es_chollo, motivo = analizar_chollo(titulo, descripcion)

        if es_chollo:
            msg = (
                f"🚨 <b>POSIBLE ERROR / CHOLLO EXTREMO</b> 🚨\n\n"
                f"📦 <b>{titulo}</b>\n"
                f"🎯 Motivo: <i>{motivo}</i>\n"
                f"🔗 <a href='{enlace}'>Ir al chollo ahora</a>"
            )
            enviar_telegram(msg)
            print("Alerta enviada:", titulo)
            historial.append(enlace)

    guardar_historial(historial)

if __name__ == "__main__":
    escanear()
