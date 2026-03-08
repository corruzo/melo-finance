import sys
import os
sys.path.append(os.getcwd())

from scraper import update_bcv_rate_if_needed
from database import SessionLocal

db = SessionLocal()
try:
    print("Iniciando update_bcv_rate_if_needed...")
    rate = update_bcv_rate_if_needed(db)
    print("Tasa obtenida:", rate)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
