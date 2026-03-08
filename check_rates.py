import sys
import os
sys.path.append(os.getcwd())

from database import SessionLocal, Rate

db = SessionLocal()
rates = db.query(Rate).all()
for r in rates:
    print(r.fecha, r.valor_bs_bcv)
