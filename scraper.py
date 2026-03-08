import requests
from datetime import date
from sqlalchemy.orm import Session
from database import Rate, SessionLocal

# Cache simple en memoria (dura hasta que el servidor se reinicia)
_rate_cache = {
    "date": None,
    "value": None
}

def get_rate_from_dolarapi() -> float:
    """
    Fuente Principal: API de DolarApi.com - Totalmente confiable y rápida.
    Devuelve la tasa oficial BCV del día actual.
    """
    try:
        response = requests.get(
            "https://ve.dolarapi.com/v1/dolares/oficial",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        promedio = data.get("promedio")
        if promedio and promedio > 0:
            print(f"RATE: Tasa obtenida de DolarApi.com: {promedio}")
            return float(promedio)
        return None
    except Exception as e:
        print(f"RATE: Error en DolarApi.com: {e}")
        return None


def get_rate_from_bcv_scrape() -> float:
    """
    Fuente de Respaldo: Scraping directo del BCV.
    Puede fallar si el BCV bloquea el servidor (common on Railway).
    """
    try:
        from bs4 import BeautifulSoup
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get("https://www.bcv.org.ve/", headers=headers, verify=False, timeout=8)
        response.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        dolar_div = soup.find('div', id='dolar')
        if dolar_div:
            valor_text = dolar_div.find('strong').text.strip()
            valor_limpio = valor_text.replace('.', '').replace(',', '.')
            rate = float(valor_limpio)
            print(f"RATE: Tasa obtenida de BCV scrape: {rate}")
            return rate
        return None
    except Exception as e:
        print(f"RATE: Error en BCV scrape: {e}")
        return None


def update_bcv_rate_if_needed(db: Session = None) -> float:
    """
    Obtiene y persiste la tasa del dólar del día.
    Estrategia:
    1. Cache en memoria (instantáneo)
    2. Base de datos (si ya fue guardada hoy)
    3. DolarApi.com (API confiable, fuente primaria)
    4. BCV scraping (respaldo)
    5. Última tasa conocida de la DB
    6. 0.0 si todo falla (el sistema no se cae)
    """
    today = date.today()

    # 1. Memory Cache
    if _rate_cache["date"] == today and _rate_cache["value"]:
        return _rate_cache["value"]

    # Creamos una sesión local en lugar de usar la del request para evitar `database is locked`
    # o comitear prematuramente cambios pendientes del request principal.
    local_db = SessionLocal()

    try:
        # 2. Base de Datos (ya fue guardada hoy)
        existing_rate = local_db.query(Rate).filter(Rate.fecha == today).first()
        if existing_rate and existing_rate.valor_bs_bcv > 0:
            _rate_cache["date"] = today
            _rate_cache["value"] = existing_rate.valor_bs_bcv
            return _rate_cache["value"]

        # 3 & 4. Obtener tasa fresca (DolarAPI primero, BCV como respaldo)
        # Bajar el timeout para evitar colgar la página.
        rate_value = get_rate_from_dolarapi() or get_rate_from_bcv_scrape()

        if rate_value and rate_value > 0:
            # Guardar o actualizar en DB
            if existing_rate:
                existing_rate.valor_bs_bcv = rate_value
            else:
                local_db.add(Rate(fecha=today, valor_bs_bcv=rate_value))
            local_db.commit()
            _rate_cache["date"] = today
            _rate_cache["value"] = rate_value
            return rate_value

        # 5. Última tasa conocida de la DB
        last_rate = local_db.query(Rate).order_by(Rate.fecha.desc()).first()
        if last_rate and last_rate.valor_bs_bcv > 0:
            print(f"RATE: Usando última tasa conocida: {last_rate.valor_bs_bcv}")
            _rate_cache["date"] = today
            _rate_cache["value"] = last_rate.valor_bs_bcv
            return last_rate.valor_bs_bcv

        # 6. Fallback total
        print("RATE: No se pudo obtener tasa. Usando 0.0")
        return 0.0

    except Exception as e:
        print(f"RATE: Error crítico en update_bcv_rate_if_needed: {e}")
        return 0.0
    finally:
        local_db.close()
