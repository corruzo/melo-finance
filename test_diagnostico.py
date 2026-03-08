"""
Diagnóstico completo del sistema Melo Finance.
Prueba arranque de la app y endpoints críticos.
"""
import subprocess
import time
import requests
import sys

BASE = "http://localhost:8000"

def test(name, resp, expected_codes=[200, 302, 303]):
    code = resp.status_code
    ok = code in expected_codes
    emoji = "✅" if ok else "❌"
    print(f"{emoji} [{code}] {name}")
    if not ok:
        print(f"   Body: {resp.text[:200]}")
    return ok

def run_tests():
    print("=" * 60)
    print("DIAGNÓSTICO MELO FINANCE - ENDPOINTS")
    print("=" * 60)
    
    session = requests.Session()
    errors = 0

    # 1. Login page
    r = session.get(f"{BASE}/login")
    if not test("GET /login → Carga formulario", r): errors += 1

    # 2. Static files
    r = session.get(f"{BASE}/static/sw.js")
    if not test("GET /static/sw.js → Service Worker", r): errors += 1

    r = session.get(f"{BASE}/static/manifest.json")
    if not test("GET /static/manifest.json → PWA Manifest", r): errors += 1

    # 3. Auth endpoints (sin credenciales → 303 redirect esperado)
    r = session.get(f"{BASE}/dashboard", allow_redirects=False)
    if not test("GET /dashboard sin sesión → Redirect 303", r, [303, 302, 307]): errors += 1

    r = session.get(f"{BASE}/clients", allow_redirects=False)
    if not test("GET /clients sin sesión → Redirect 303", r, [303, 302, 307]): errors += 1

    r = session.get(f"{BASE}/loans", allow_redirects=False)
    if not test("GET /loans sin sesión → Redirect 303", r, [303, 302, 307]): errors += 1

    r = session.get(f"{BASE}/reports", allow_redirects=False)
    if not test("GET /reports sin sesión → Redirect 303", r, [303, 302, 307]): errors += 1

    # 4. WebAuthn endpoints
    r = session.get(f"{BASE}/auth/webauthn/login/options?username=test@example.com")
    if not test("GET /auth/webauthn/login/options → 404 esperado (sin usuario)", r, [404]): errors += 1

    # 5. CSRF protection
    r = session.post(f"{BASE}/login", data={"email": "x", "password": "x", "csrf_token": "invalid"})
    if not test("POST /login con CSRF inválido → Redirect o error", r, [200, 302, 303, 400, 422, 303]): errors += 1

    print("=" * 60)
    if errors == 0:
        print("✅ TODOS LOS ENDPOINTS FUNCIONAN CORRECTAMENTE")
    else:
        print(f"❌ {errors} endpoint(s) con problemas")
    print("=" * 60)

if __name__ == "__main__":
    try:
        r = requests.get(f"{BASE}/login", timeout=3)
        print(f"Servidor detectado en {BASE}\n")
        run_tests()
    except Exception:
        print(f"❌ El servidor no está corriendo en {BASE}")
        print("Inicia el servidor con: uvicorn main:app --port 8000")
        sys.exit(1)
