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

# --- RADAR 1: CHOLLOMETRO (Errores de precio globales y >= 80%) ---
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
                enlace = "https://www.chollometro.com" + enlace

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

# --- RADAR 2: DEPORVILLAGE OUTLET (0€ o >= 75% de descuento) ---
def escanear_deporvillage(historial):
    # Puedes cambiar esta URL por una categoría concreta (ej. /zapatillas-running-outlet)
    url = "https://www.deporvillage.com/outlet"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        print("Deporvillage status:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscamos todos los enlaces a fichas de producto dentro de la cuadrícula
        enlaces_vistos = set()
        productos_detectados = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Las fichas de producto de Deporvillage tienen formato /nombre-del-producto
            if href.startswith("/") and len(href) > 15 and ":" not in href and "/outlet" not in href:
                tarjeta = a.find_parent(["article", "li", "div"])
                if not tarjeta:
                    continue

                texto_tarjeta = tarjeta.get_text(" ", strip=True)
                if "€" not in texto_tarjeta or len(texto_tarjeta) > 350:
                    continue

                enlace_completo = "https://www.deporvillage.com" + href
                if enlace_completo in enlaces_vistos:
                    continue
                enlaces_vistos.add(enlace_completo)
                productos_detectados += 1

                if enlace_completo in historial:
                    continue

                # Extraer precios que aparezcan en la tarjeta (ej. "24,95 €" y "99,95 €")
                precios_encontrados = re.findall(r"(\d+[.,]\d{2})\s*€", texto_tarjeta)
                valores = [float(p.replace(",", ".")) for p in precios_encontrados]

                # Extraer porcentaje si aparece (ej. "-75%")
                descuento = 0
                for d in re.findall(r"-?\s*(\d{2})\s*%", texto_tarjeta):
                    if int(d) > descuento:
                        descuento = int(d)

                if len(valores) >= 2:
                    precio_actual = min(valores)
                    precio_original = max(valores)
                    if precio_original > precio_actual:
                        calc = round(((precio_original - precio_actual) / precio_original) * 100)
                        if calc > descuento:
                            descuento = calc
                elif len(valores) == 1:
                    precio_actual = valores[0]
                else:
                    continue

                # Condición: precio 0€ o descuento >= 75%
                if precio_actual == 0.0 or descuento >= 75:
                    titulo = a.get("title") or a.get_text(strip=True) or "Producto Deporvillage"
                    msg = (
                        f"🏃‍♂️ <b>CHOLLO EN DEPORVILLAGE</b> 🏃‍♂️\n\n"
                        f"📦 <b>{titulo}</b>\n"
                        f"💰 Precio: <b>{precio_actual:.2f} €</b> ({descuento}% dto.)\n"
                        f"🔗 <a href='{enlace_completo}'>Ver en Deporvillage</a>"
                    )
                    enviar_telegram(msg)
                    historial.append(enlace_completo)

        print(f"Deporvillage productos analizados: {productos_detectados}")
    except Exception as e:
        print("Error en Deporvillage:", e)

if __name__ == "__main__":
    hist = cargar_historial()
    escanear_chollometro(hist)
    escanear_deporvillage(hist)
    guardar_historial(hist)
