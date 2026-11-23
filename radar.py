import os
import re
import json
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ARCHIVO_HISTORIAL = "historial.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9"
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
        json.dump(historial[-500:], f, indent=2)

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

def limpiar_precio(texto):
    limpio = re.sub(r"[^\d,]", "", texto).replace(",", ".")
    try:
        return float(limpio) if limpio else None
    except ValueError:
        return None

def escanear_chollometro():
    historial = cargar_historial()
    url = "https://chollometro.com"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        print("Chollometro status:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        articulos = soup.find_all("article")
        print(f"Chollometro publicaciones: {len(articulos)}")

        for art in articulos:
            enlace_el = art.select_one("a.cept-tt, a[href*='/ofertas/'], a[href*='/cupones/']")
            if not enlace_el:
                continue

            titulo = enlace_el.get_text(strip=True)
            enlace = enlace_el.get("href", "")
            if enlace.startswith("/"):
                enlace = "https://chollometro.com" + enlace

            if not enlace or enlace in historial:
                continue

            texto_lower = art.get_text(" ", strip=True).lower()
            precio_el = art.select_one(".thread-price, .cept-tp")
            precio_texto = precio_el.get_text(strip=True) if precio_el else ""
            precio_actual = limpiar_precio(precio_texto)

            precio_ant_el = art.select_one(".mute--text.text--lineThrough, .cept-next-best-price")
            precio_anterior = limpiar_precio(precio_ant_el.get_text(strip=True)) if precio_ant_el else None

            descuento = 0
            if precio_actual is not None and precio_anterior and precio_anterior > precio_actual:
                descuento = round(((precio_anterior - precio_actual) / precio_anterior) * 100)

            for p in re.findall(r"(\d{2,3})\s*%", texto_lower):
                if descuento < int(p) <= 100:
                    descuento = int(p)

            es_gratis = (precio_actual == 0.0) or any(w in texto_lower for w in ["gratis", "0€", "0 €", "error de precio", "bug"])
            if es_gratis or descuento >= 80:
                etiqueta_precio = precio_texto if precio_texto else "Ver en enlace"
                info_dto = f" ({descuento}% dto.)" if descuento > 0 else ""
                msg = (
                    f"🚨 <b>CHOLLO DETECTADO</b> 🚨\n\n"
                    f"📦 <b>{titulo}</b>\n"
                    f"💰 Precio: <b>{etiqueta_precio}</b>{info_dto}\n"
                    f"🔗 <a href='{enlace}'>Ir al chollo</a>"
                )
                enviar_telegram(msg)
                print("Alerta enviada:", titulo)
                historial.append(enlace)

        guardar_historial(historial)
    except Exception as e:
        print("Error en Chollometro:", e)

if __name__ == "__main__":
    escanear_chollometro()
