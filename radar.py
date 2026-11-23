import os
import re
import json
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ARCHIVO_HISTORIAL = "historial.json"

URL_RSS = "https://chollometro.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
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
    palabras_clave = [
        "error de precio", "0€", "0 €", "0,00€", "0,00 €", 
        "gratis", "100% dto", "100% de descuento", "chollazo"
    ]
    for palabra in palabras_clave:
        if palabra in todo_el_texto:
            return True, f"Palabra clave: '{palabra}'"

    # 2. Buscar porcentajes de descuento del 80% al 100%
    descuentos = re.findall(r"(\d{2,3})\s*%", todo_el_texto)
    for d in descuentos:
        if 80 <= int(d) <= 100:
            return True, f"Descuento extremo: {d}%"

    return False, ""

def escanear():
    historial = cargar_historial()
    respuesta = requests.get(URL_RSS, headers=HEADERS, timeout=20)
    print("Código de respuesta de Chollometro:", respuesta.status_code)

    # Usamos BeautifulSoup en modo HTML/XML tolerante a fallos
    soup = BeautifulSoup(respuesta.text, "html.parser")
    items = soup.find_all("item")
    print(f"Chollos encontrados para analizar: {len(items)}")

    if len(items) == 0:
        print("Aviso: No se encontraron items. Primeras letras recibidas:", respuesta.text[:200])

    for item in items:
        titulo_tag = item.find("title")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sin título"
        
        # En BeautifulSoup html.parser el enlace suele ir justo detrás de <link>
        link_tag = item.find("link")
        enlace = link_tag.next_sibling.strip() if (link_tag and link_tag.next_sibling) else ""
        if not enlace.startswith("http"):
            guid_tag = item.find("guid")
            enlace = guid_tag.get_text(strip=True) if guid_tag else ""

        desc_tag = item.find("description")
        descripcion = desc_tag.get_text() if desc_tag else ""

        if not enlace or enlace in historial:
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
