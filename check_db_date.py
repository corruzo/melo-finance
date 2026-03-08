import sys
import os
sys.path.append(os.getcwd())

from database import SessionLocal, Rate
from datetime import date

db = SessionLocal()
today = date.today()
print("Today is:", today)
rate = db.query(Rate).filter(Rate.fecha == today).first()
if rate:
    print("Found exact date match in DB:", rate.valor_bs_bcv)
else:
    print("Not found matching exactly for today")
