import sys
import os
sys.path.append(os.getcwd())

from scraper import get_rate_from_dolarapi, update_bcv_rate_if_needed

print("=== Test 1: DolarAPI ===")
rate = get_rate_from_dolarapi()
print(f"Resultado: {rate}")

print("\n=== Test 2: update_bcv_rate_if_needed ===")
rate2 = update_bcv_rate_if_needed()
print(f"Resultado: {rate2}")
