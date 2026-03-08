"""
Prueba aislada del endpoint webauthn/login/options
"""
import sys, os
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Test 1: Endpoint con usuario que no existe → 404
r = client.get("/auth/webauthn/login/options?username=noexiste@test.com")
print(f"Test 1 (usuario no existe): {r.status_code} - esperado 404")
if r.status_code == 500:
    print(f"  ERROR 500: {r.text[:500]}")

# Test 2: Login page
r = client.get("/login")
print(f"Test 2 (login page): {r.status_code} - esperado 200")

# Test 3: Dashboard sin auth → redirect 
r = client.get("/dashboard", allow_redirects=False)
print(f"Test 3 (dashboard sin auth): {r.status_code} - esperado 303/302")

# Test 4: WebAuthn register sin auth → redirect
r = client.get("/auth/webauthn/register/options", allow_redirects=False)
print(f"Test 4 (register sin auth): {r.status_code} - esperado 303/401")

print("\nDiagnóstico completado.")
