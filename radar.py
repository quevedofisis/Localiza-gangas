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
        json.dump(historial[-800:], f, indent=2)

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

# --- RADAR 1: CHOLLOMETRO (Errores globales y >= 80%) ---
def escanear_chollometro(historial):
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
                    f"🚨 <b>CHOLLO DETECTADO (Chollometro)</b> 🚨\n\n"
                    f"📦 <b>{titulo}</b>\n"
                    f"💰 Precio: <b>{etiqueta_precio}</b>{info_dto}\n"
                    f"🔗 <a href='{enlace}'>Ir al chollo</a>"
                )
                enviar_telegram(msg)
                historial.append(enlace)
    except Exception as e:
        print("Error en Chollometro:", e)

# --- RADAR 2: TIENDAS DE PÁDEL (0€ o >= 80% de descuento) ---
def escanear_tienda_padel(nombre_tienda, url_outlet, dominio_base, selector_tarjeta, historial):
    try:
        resp = requests.get(url_outlet, headers=HEADERS, timeout=20)
        print(f"{nombre_tienda} status:", resp.status_code)
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        tarjetas = soup.select(selector_tarjeta)
        print(f"{nombre_tienda} productos detectados: {len(tarjetas)}")

        for item in tarjetas:
            enlace_el = item.select_one("a[href]")
            if not enlace_el:
                continue

            enlace = enlace_el.get("href", "").strip()
            if enlace.startswith("/"):
                enlace = dominio_base + enlace

            if not enlace.startswith("http") or enlace in historial:
                continue

            titulo_el = item.select_one("h2, h3, .product-title, .product-name, .name")
            titulo = titulo_el.get_text(strip=True) if titulo_el else (enlace_el.get("title") or enlace_el.get_text(strip=True))
            if not titulo or len(titulo) < 4:
                continue

            texto_tarjeta = item.get_text(" ", strip=True)

            precios_raw = re.findall(r"(\d+[.,]\d{2})\s*€", texto_tarjeta)
            valores = [float(p.replace(",", ".")) for p in precios_raw]

            descuento = 0
            for d in re.findall(r"-?\s*(\d{2,3})\s*%", texto_tarjeta):
                if descuento < int(d) <= 100:
                    descuento = int(d)

            if len(valores) >= 2:
                precio_actual = min(valores)
                precio_original = max(valores)
                if precio_original > precio_actual:
                    calc = round(((precio_original - precio_actual) / precio_original) * 100)
                    if calc > descuento:
                        descuento = calc
            elif len(valores) == 1:
                precio_actual = valores
            else:
                continue

            # CONDICIÓN DE ALERTA: Precio 0€ o descuento >= 80%
            if precio_actual == 0.0 or descuento >= 80:
                msg = (
                    f"🎾 <b>CHOLLO PÁDEL ({nombre_tienda})</b> 🎾\n\n"
                    f"📦 <b>{titulo}</b>\n"
                    f"💰 Precio: <b>{precio_actual:.2f} €</b> ({descuento}% dto.)\n"
                    f"🔗 <a href='{enlace}'>Ver en {nombre_tienda}</a>"
                )
                enviar_telegram(msg)
                print(f"Alerta enviada ({nombre_tienda}):", titulo)
                historial.append(enlace)

    except Exception as e:
        print(f"Error en {nombre_tienda}:", e)

if __name__ == "__main__":
    hist = cargar_historial()

    # 1. Chollometro general
    escanear_chollometro(hist)

    # 2. Padelmania Outlet
    escanear_tienda_padel(
        nombre_tienda="Padelmania",
        url_outlet="https://padelmania.com",
        dominio_base="https://padelmania.com",
        selector_tarjeta="article.product-miniature, .product-container, .ajax_block_product",
        historial=hist
    )

    # 3. Pádel Ibérico Outlet
    escanear_tienda_padel(
        nombre_tienda="Pádel Ibérico",
        url_outlet="https://padeliberico.es",
        dominio_base="https://padeliberico.es",
        selector_tarjeta="article.product-miniature, .product-container, .ajax_block_product",
        historial=hist
    )

    guardar_historial(hist)
