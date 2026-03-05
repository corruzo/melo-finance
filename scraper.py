import requests
from bs4 import BeautifulSoup
from datetime import date
from sqlalchemy.orm import Session
from database import Rate, SessionLocal
import urllib3

# Desactivar advertencias de SSL en caso de que BCV presente certificados inseguros
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_bcv_rate() -> float:
    """Extrae el precio del USD desde el sitio web del BCV (bcv.org.ve)"""
    url = "https://www.bcv.org.ve/"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Algunas veces el BCV tiene problemas SSL, verify=False lo previene.
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # El DIV con el valor del dólar en la web del BCV tiene ID 'dolar'
        dolar_div = soup.find('div', id='dolar')
        if dolar_div:
            # Extraemos del <strong> y limpiamos el string
            valor_text = dolar_div.find('strong').text.strip()
            # El valor de Bs viene con comas para decimales, ejemplo: "36,25300000"
            valor_limpio = valor_text.replace('.', '').replace(',', '.')
            return float(valor_limpio)
        else:
            print("No se encontró el contenedor del dólar en el HTML.")
            return None
            
    except Exception as e:
        print(f"Error extrayendo tasa del BCV: {e}")
        return None

def update_bcv_rate_if_needed(db: Session = None):
    """
    Verifica si la tasa del día actual ya se encuentra en la DB.
    Si no existe, la extrae usando web scraping y la guarda para evitar llamadas repetitivas.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        today = date.today()
        # Verificar si la tasa de hoy ya está en base de datos
        existing_rate = db.query(Rate).filter(Rate.fecha == today).first()
        if existing_rate:
            return existing_rate.valor_bs_bcv
            
        # Si no está, hacer el scrapeo
        rate_value = get_bcv_rate()
        if rate_value:
            new_rate = Rate(fecha=today, valor_bs_bcv=rate_value)
            db.add(new_rate)
            db.commit()
            db.refresh(new_rate)
            return new_rate.valor_bs_bcv
            
        # Si falla el scrapeo, devolver la última tasa guardada
        last_rate = db.query(Rate).order_by(Rate.fecha.desc()).first()
        if last_rate:
            return last_rate.valor_bs_bcv
            
        # Si no hay absolutamente nada
        return 0.0
    finally:
        if close_db:
            db.close()
