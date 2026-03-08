from fastapi import FastAPI, Depends, Request, Form, HTTPException, status, Response, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import shutil
from typing import List
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from database import engine, Base, get_db, init_db, User, Client, Loan, Transaction, Rate, CapitalTransaction, Notification, LoanAttachment, WebAuthnCredential, PushSubscription
import schemas
from scraper import update_bcv_rate_if_needed
import utils
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import analytics_engine
import json
import base64
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
)
from pywebpush import webpush, WebPushException

# --- Seguridad ---
_SECRET_KEY_FALLBACK = "melo-finance-secret-key-change-in-production"
SECRET_KEY = os.environ.get("MELO_SECRET_KEY", _SECRET_KEY_FALLBACK)
if SECRET_KEY == _SECRET_KEY_FALLBACK and os.environ.get("RAILWAY_ENVIRONMENT") == "production":
    print("WARNING: Using default SECRET_KEY in production! Set MELO_SECRET_KEY for safety.")

signer = URLSafeTimedSerializer(SECRET_KEY)

# --- Configuración WebAuthn (Biometría) ---
RP_ID = os.environ.get("RP_ID", "melo-finance.up.railway.app") if os.environ.get("RAILWAY_ENVIRONMENT") == "production" else "localhost"
RP_NAME = "Melo Finance"
ORIGIN = f"https://{RP_ID}" if os.environ.get("RAILWAY_ENVIRONMENT") == "production" else f"http://{RP_ID}:8000"

# --- Configuración WebPush (Notificaciones) ---
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {"sub": "mailto:nixon@melo-finance.com"}

if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
    print("WARNING: VAPID keys not set. Push notifications disabled.")
    VAPID_PUBLIC_KEY = "" # Evitar errores en templates


# --- CSRF & Security Helpers ---
def generate_csrf_token():
    return signer.dumps(os.urandom(16).hex())

def verify_csrf_token(token: str) -> bool:
    try:
        signer.loads(token, max_age=3600) # 1 hora de validez
        return True
    except:
        return False

# Rate Limiter Simple (En memoria para la Beta)
from collections import defaultdict
import time
_login_attempts = defaultdict(list)

def check_rate_limit(ip: str):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < 60] # Ventana de 1 min
    if len(_login_attempts[ip]) >= 5: # Máximo 5 intentos por minuto
        return False
    _login_attempts[ip].append(now)
    return True

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    # Compatibilidad rógresiva: si no está hasheado (prefijo bcrypt), comparar texto plano y re-hashear
    if not hashed.startswith("$2b$"):
        return plain == hashed
    plain_bytes = plain.encode('utf-8')[:72]
    try:
        return bcrypt.checkpw(plain_bytes, hashed.encode('utf-8'))
    except ValueError:
        return False

# Crear tablas en caso de no existir e informar estatus
try:
    init_db()
    print("DATABASE: Conexión exitosa y tablas verificadas.")
except Exception as e:
    print(f"DATABASE ERROR: Falló la inicialización - {e}")

app = FastAPI(title="Melo Préstamos - Bimoneda", description="App de gestión de préstamos USD/VES", version="1.0.0")

# Montar static para CSS y JS
if not os.path.exists("./static"):
    os.makedirs("./static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Directorio de subidas (archivos de préstamos)
UPLOAD_DIR = os.path.join("static", "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Templates (Stitch)
if not os.path.exists("./templates"):
    os.makedirs("./templates")
templates = Jinja2Templates(directory="templates")

def format_currency(value):
    try:
        if value is None:
            return "0,00"
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return value

templates.env.filters["format_currency"] = format_currency

# --- Helpers ---
def crear_alerta(db: Session, user_id: int, titulo: str, mensaje: str, tipo: str = "info"):
    new_notif = Notification(user_id=user_id, titulo=titulo, mensaje=mensaje, tipo=tipo)
    db.add(new_notif)
    db.commit()

# Utilidad: Interés calculado (simple)
def calculate_interest(loan: Loan) -> float:
    """Calcula el interés base usando el % sobre el monto principal"""
    return loan.monto_principal * (loan.porcentaje_interes / 100)

@app.on_event("startup")
def startup_event():
    """Al iniciar, corremos el scraper si es necesario."""
    db = next(get_db())
    # Chequear e inicializar si es necesario la tasa actual del BCV
    update_bcv_rate_if_needed(db)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if not token:
        return None
    try:
        user_id = signer.loads(token, max_age=60 * 60 * 24 * 30)  # 30 días
    except (BadSignature, SignatureExpired):
        return None
    return db.query(User).filter(User.id == user_id).first()

def require_user(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return current_user

# --- Endpoints de Biometría (WebAuthn) ---

@app.get("/auth/webauthn/register/options")
def webauthn_register_options(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Genera las opciones para registrar una nueva credencial biométrica."""
    if not current_user.webauthn_id:
        current_user.webauthn_id = os.urandom(16).hex()
        db.commit()

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=bytes.fromhex(current_user.webauthn_id),
        user_name=current_user.username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )
    
    json_options = options_to_json(options)
    res = Response(content=json_options, media_type="application/json")
    # Guardamos el challenge en una cookie temporal para verificar luego
    res.set_cookie("reg_options", signer.dumps(json_options), max_age=300, httponly=True, secure=True if RP_ID != "localhost" else False)
    return res

@app.post("/auth/webauthn/register/verify")
async def webauthn_register_verify(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Verifica y guarda la nueva credencial biométrica."""
    data = await request.json()
    options_cookie = request.cookies.get("reg_options")
    if not options_cookie:
        raise HTTPException(status_code=400, detail="Sesión de registro expirada")
    
    try:
        options_json = json.loads(signer.loads(options_cookie))
        registration_verification = verify_registration_response(
            credential=data,
            expected_challenge=base64.urlsafe_b64decode(options_json["challenge"] + "=="),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )
        
        # Guardar en base de datos
        new_cred = WebAuthnCredential(
            user_id=current_user.id,
            credential_id=registration_verification.credential_id.hex(),
            public_key=base64.b64encode(registration_verification.credential_public_key).decode('utf-8'),
            sign_count=registration_verification.sign_count,
        )
        db.add(new_cred)
        db.commit()
        return {"status": "ok", "message": "Biometría registrada correctamente"}
    except Exception as e:
        print(f"WEBAUTHN REG ERROR: {e}")
        raise HTTPException(status_code=400, detail="Error al verificar biometría")

@app.get("/auth/webauthn/login/options")
def webauthn_login_options(username: str, db: Session = Depends(get_db)):
    """Genera opciones para iniciar sesión con biometría."""
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.credentials:
        raise HTTPException(status_code=404, detail="Usuario no tiene biometría configurada")

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=bytes.fromhex(c.credential_id), type="public-key")
            for c in user.credentials
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    
    json_options = options_to_json(options)
    res = Response(content=json_options, media_type="application/json")
    res.set_cookie("auth_options", signer.dumps(json_options), max_age=300, httponly=True, secure=True if RP_ID != "localhost" else False)
    res.set_cookie("auth_user", str(user.id), max_age=300, httponly=True)
    return res

@app.post("/auth/webauthn/login/verify")
async def webauthn_login_verify(request: Request, db: Session = Depends(get_db)):
    """Verifica la firma biométrica e inicia sesión."""
    data = await request.json()
    options_cookie = request.cookies.get("auth_options")
    user_id_cookie = request.cookies.get("auth_user")
    
    if not options_cookie or not user_id_cookie:
        raise HTTPException(status_code=400, detail="Sesión biométrica expirada")
    
    user = db.query(User).filter(User.id == int(user_id_cookie)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        options_json = json.loads(signer.loads(options_cookie))
        # El credential_id en el response viene en base64url format
        cred_id_raw = data["rawId"]  # base64url string
        # Decodificar de base64url a bytes y luego a hex para buscar en DB
        import base64
        cred_id_bytes = base64.urlsafe_b64decode(cred_id_raw + "==")
        cred_id_hex = cred_id_bytes.hex()
        
        db_cred = db.query(WebAuthnCredential).filter(WebAuthnCredential.credential_id == cred_id_hex).first()
        if not db_cred:
             raise HTTPException(status_code=404, detail="Credencial no reconocida")

        authentication_verification = verify_authentication_response(
            credential=data,
            expected_challenge=base64.urlsafe_b64decode(options_json["challenge"] + "=="),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=base64.b64decode(db_cred.public_key),
            credential_current_sign_count=db_cred.sign_count,
        )
        
        # Actualizar contador
        db_cred.sign_count = authentication_verification.new_sign_count
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Iniciar sesión (estilo melo-finance)
        token = signer.dumps(user.id)
        res = Response(content=json.dumps({"status": "ok"}), media_type="application/json")
        res.set_cookie("session_token", token, max_age=60 * 60 * 24 * 30, httponly=True, secure=True if RP_ID != "localhost" else False)
        return res
    except Exception as e:
        print(f"WEBAUTHN LOGIN ERROR: {e}")
        raise HTTPException(status_code=400, detail="Firma biométrica inválida")

@app.post("/push/subscribe")
async def push_subscribe(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Guarda una nueva suscripción push del navegador."""
    try:
        data = await request.json()
        # Verificar si ya existe
        existing = db.query(PushSubscription).filter(PushSubscription.endpoint == data["endpoint"]).first()
        if existing:
            return {"status": "ok", "message": "Ya suscrito"}
        
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=data["endpoint"],
            auth_key=data["keys"]["auth"],
            p256dh_key=data["keys"]["p256dh"],
            browser=request.headers.get("user-agent", "unknown")
        )
        db.add(new_sub)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        print(f"SUBSCRIBE ERROR: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/push/test")
def push_test(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Envía una notificación de prueba para verificar que el sistema funciona."""
    if not current_user or not current_user.push_subscriptions:
        return {"status": "error", "message": "No hay suscripciones activas en este dispositivo."}
    
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return {"status": "error", "message": "VAPID Keys no configuradas en el servidor."}

    sent_count = 0
    expired_count = 0
    for sub in current_user.push_subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"auth": sub.auth_key, "p256dh": sub.p256dh_key}
                },
                data=json.dumps({
                    "title": "Melo Finance 🚀",
                    "body": "¡Notificaciones push activadas correctamente!",
                    "url": "/dashboard"
                }),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            sent_count += 1
        except WebPushException as ex:
            print(f"PUSH TEST ERROR: {ex}")
            if ex.response and ex.response.status_code in [404, 410]:
                db.delete(sub)
                expired_count += 1
    
    db.commit()
    return {"status": "ok", "sent": sent_count, "deleted_expired": expired_count}


@app.get("/", response_class=RedirectResponse)
def index():
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    csrf_token = generate_csrf_token()
    return templates.TemplateResponse("login.html", {"request": request, "csrf_token": csrf_token})

@app.post("/login")
def login_post(
    request: Request,
    email: str = Form(""), 
    password: str = Form(""), 
    csrf_token: str = Form(""),
    db: Session = Depends(get_db)
):
    # 1. Verificar CSRF
    if not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF Token inválido")
    
    # 2. Rate Limit
    if not check_rate_limit(request.client.host):
        return RedirectResponse(url="/login?error=too_many_requests", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(User).filter(User.username == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return RedirectResponse(url="/login?error=1", status_code=status.HTTP_303_SEE_OTHER)
    
    # Re-hashear contraseñas en texto plano que ya existían (migración automática)
    if not user.hashed_password.startswith("$2b$"):
        user.hashed_password = hash_password(password)
        db.commit()
    
    # Cookie firmada y con tiempo de expiración
    token = signer.dumps(user.id)
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    # Hardening de cookies para producción
    is_prod = os.environ.get("RAILWAY_ENVIRONMENT") == "production"
    response.set_cookie(
        key="session_token", 
        value=token, 
        path="/",
        httponly=True,
        samesite="lax",
        secure=is_prod, # Solo HTTPS en producción
        max_age=60 * 60 * 12 # Reducido a 12 horas para mayor seguridad financiera
    )
    return response

@app.get("/signup", response_class=HTMLResponse)
def signup_get(request: Request):
    csrf_token = generate_csrf_token()
    return templates.TemplateResponse("sign-up.html", {"request": request, "csrf_token": csrf_token})

@app.post("/signup")
def signup_post(
    nombre: str = Form(""), 
    apellido: str = Form(""), 
    email: str = Form(""), 
    password: str = Form(""), 
    csrf_token: str = Form(""),
    db: Session = Depends(get_db)
):
    if not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF Token inválido")
    existing = db.query(User).filter(User.username == email).first()
    if existing:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    user = User(
        username=email, 
        nombre=nombre, 
        apellido=apellido, 
        hashed_password=hash_password(password),
        capital_total_usd=0.0,
        capital_total_ves=0.0
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = signer.dumps(user.id)
    response = RedirectResponse(url="/settings/capital", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="session_token", value=token, path="/",
        httponly=True, samesite="lax",
        max_age=60 * 60 * 24 * 30
    )
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """
    Ruta Principal de Dashboard.
    """
    user = current_user
        
    # Si ambos capitales están en cero, pedir configurarlo
    if user.capital_total_usd == 0 and user.capital_total_ves == 0:
        return RedirectResponse(url="/settings/capital")
        
    tasa_actual = update_bcv_rate_if_needed(db)
    
    capital_inicial = user.capital_total_usd
    
    # Préstamos activos con transacciones ya cargadas (Evita N+1 query problem)
    active_loans = db.query(Loan).options(joinedload(Loan.transactions)).join(Client).filter(Client.user_id == user.id, Loan.estatus == 'activo').all()
    
    prestamos_vencidos = sum(1 for l in active_loans if utils.chequear_cuota_vencida(l))
    total_prestamos_activos = len(active_loans)
    
    # Capital Prestado (Solo el capital principal que aún no fue recuperado)
    capital_prestado_usd = sum(max(0.0, l.monto_principal - sum(t.monto for t in l.transactions if t.tipo == 'pago_cuota')) for l in active_loans)

    # Ganancias proyectadas = interes sumado de préstamos activos
    ganancias_proyectadas = sum(
        utils.calcular_interes_simple(l.monto_principal, l.porcentaje_interes) * (l.cuotas_totales or 1)
        for l in active_loans
    )
    
    # Ganancias reales = Interés recolectado (Total pagado - Principal cubierto)
    ganancias_reales = 0.0
    all_user_loans = db.query(Loan).join(Client).filter(Client.user_id == user.id).all()
    for l in all_user_loans:
        pagos_usd = sum(t.monto for t in l.transactions if t.tipo == 'pago_cuota')
        if pagos_usd > l.monto_principal:
            ganancias_reales += (pagos_usd - l.monto_principal)
    
    # Notificaciones no leídas
    unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.leida == False).count()

    # Los capitales ya están en el modelo User
    disponible_usd = user.capital_total_usd
    disponible_ves = user.capital_total_ves

    # Datos para el gráfico: Últimos 7 meses (Pagos reales)
    meses_labels = []
    meses_valores = []
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    hoy = datetime.utcnow()
    
    current_month = datetime(hoy.year, hoy.month, 1)
    
    for i in range(6, -1, -1):
        # Calcular mjes retrospectivo con seguridad para enero/febrero
        target_m = current_month.month - i - 1
        target_y = current_month.year + (target_m // 12)
        target_m = (target_m % 12) + 1
        
        mes_label = meses_nombres[target_m - 1]
        meses_labels.append(mes_label)
        
        start = datetime(target_y, target_m, 1)
        if target_m == 12:
            end = datetime(target_y + 1, 1, 1)
        else:
            end = datetime(target_y, target_m + 1, 1)
            
        sum_mes = db.query(func.sum(Transaction.monto)).join(Loan).join(Client).filter(
            Client.user_id == user.id,
            Transaction.tipo == 'pago_cuota',
            Transaction.fecha >= start,
            Transaction.fecha < end
        ).scalar() or 0
        meses_valores.append(sum_mes)
        
    # Normalizar valores para el gráfico % (Max es 100%)
    max_val = max(meses_valores) if meses_valores and max(meses_valores) > 0 else 1
    grafico_data = [{"label": l, "height": int((v / max_val) * 100)} for l, v in zip(meses_labels, meses_valores)]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "capital_inicial": capital_inicial,
        "disponible_usd": disponible_usd,
        "disponible_ves": disponible_ves,
        "capital_prestado_usd": capital_prestado_usd,
        "prestamos_vencidos": prestamos_vencidos,
        "total_prestamos_activos": total_prestamos_activos,
        "ganancias_proyectadas": ganancias_proyectadas,
        "ganancias_reales": ganancias_reales,
        "tasa_actual": tasa_actual,
        "unread_count": unread_count,
        "grafico_data": grafico_data,
        "user": user
    })

@app.get("/history/movements", response_class=HTMLResponse)
def movements_history_view(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    # Combinar transacciones de préstamos y transacciones de capital
    loan_trans = db.query(Transaction).join(Loan).join(Client).filter(Client.user_id == current_user.id).all()
    cap_trans = db.query(CapitalTransaction).filter(CapitalTransaction.user_id == current_user.id).all()
    
    # Formatear para una vista unificada
    for t in loan_trans:
        titulo = f"Pago: {t.loan.client.nombre}"
        tipo_mov = "entrada"
        if t.tipo == "egreso_capital":
            titulo = f"Préstamo a: {t.loan.client.nombre}"
            tipo_mov = "salida"
        elif t.tipo == "ingreso_extra":
            titulo = f"Ajuste/Anulación: {t.loan.client.nombre}"
            tipo_mov = "entrada"

        movements.append({
            "fecha": t.fecha,
            "titulo": titulo,
            "monto": t.monto_real if getattr(t, 'monto_real', None) else t.monto,
            "moneda": t.moneda,
            "tipo_ui": tipo_mov,
            "categoria": "Préstamo"
        })
    for t in cap_trans:
        movements.append({
            "fecha": t.fecha,
            "titulo": f"Ajuste de Capital",
            "monto": t.monto,
            "moneda": t.moneda,
            "tipo_ui": "entrada" if t.tipo in ["inversion", "ajuste_directo"] else "salida",
            "categoria": "Capital"
        })
        
    movements.sort(key=lambda x: x["fecha"], reverse=True)
    
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("historial-movimientos.html", {"request": request, "movements": movements, "unread_count": unread_count})

@app.get("/history/loans", response_class=HTMLResponse)
def loans_history_view(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    tasa_actual = update_bcv_rate_if_needed(db)
    loans = db.query(Loan).options(joinedload(Loan.transactions), joinedload(Loan.client)).join(Client).filter(Client.user_id == current_user.id).order_by(Loan.fecha_creacion.desc()).all()
    
    # Adaptar para multimoneda indexada
    formatted_loans = []
    for l in loans:
        monto_display = l.monto_principal
        if l.moneda == 'VES':
            monto_display = l.monto_principal * (l.tasa_bcv_snapshot or tasa_actual)
            
        formatted_loans.append({
            "id": l.id,
            "client": l.client,
            "cliente_id": l.client.id,
            "monto_principal": monto_display,
            "moneda": l.moneda,
            "fecha_creacion": l.fecha_creacion,
            "estatus": l.estatus,
            "porcentaje_interes": l.porcentaje_interes
        })
        
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("historial-prestamos.html", {"request": request, "loans": formatted_loans, "unread_count": unread_count})

@app.get("/clients", response_class=HTMLResponse)
def clients_list(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    clients = db.query(Client).options(joinedload(Client.loans).joinedload(Loan.transactions)).filter(Client.user_id == current_user.id).all()
    client_data = []
    for c in clients:
        deuda = sum(utils.obtener_deuda_pendiente(l) for l in c.loans if l.estatus == 'activo')
        client_data.append({
            "id": c.id,
            "nombre": c.nombre,
            "deuda": deuda,
            "tiene_atraso": any(utils.chequear_cuota_vencida(l) for l in c.loans if l.estatus == 'activo')
        })
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("directorio-de-clientes.html", {"request": request, "clients": client_data, "unread_count": unread_count})

@app.get("/loans", response_class=HTMLResponse)
def loans_hub(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    tasa_actual = update_bcv_rate_if_needed(db)
    active_loans = db.query(Loan).options(joinedload(Loan.transactions), joinedload(Loan.client)).join(Client).filter(Client.user_id == current_user.id, Loan.estatus == 'activo').all()
    
    # Stats
    total_prestado = sum(utils.obtener_deuda_pendiente(l) for l in active_loans)
    vencidos = sum(1 for l in active_loans if utils.chequear_cuota_vencida(l))
    
    loan_list = []
    for l in active_loans:
        # Para visualización en el Hub, mostramos en VES si el préstamo es VES
        monto_display = l.monto_principal
        deuda_display = utils.obtener_deuda_pendiente(l)
        
        if l.moneda == 'VES':
            monto_display = l.monto_principal * tasa_actual # Monto base proyectado a hoy
            deuda_display = deuda_display * tasa_actual

        loan_list.append({
            "id": l.id,
            "cliente": l.client.nombre,
            "cliente_id": l.client.id,
            "monto": monto_display,
            "deuda": deuda_display,
            "atraso": utils.chequear_cuota_vencida(l),
            "moneda": l.moneda
        })
        
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("centro-de-prestamos.html", {
        "request": request, 
        "loans": loan_list,
        "total_prestado": total_prestado,
        "vencidos": vencidos,
        "total_activos": len(active_loans),
        "tasa_actual": tasa_actual,
        "unread_count": unread_count
    })

@app.get("/settings", response_class=HTMLResponse)
def settings_view(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    return RedirectResponse(url="/settings/profile", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/clients/new", response_class=HTMLResponse)
def new_client_get(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    csrf_token = generate_csrf_token()
    return templates.TemplateResponse("nuevo-cliente.html", {"request": request, "unread_count": unread_count, "csrf_token": csrf_token})

@app.post("/clients/new")
def new_client_post(
    nombre: str = Form(...),
    cedula: str = Form(None),
    telefono: str = Form(None),
    direccion: str = Form(None),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    if not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF Token inválido")
    db_client = Client(
        nombre=nombre, 
        cedula=cedula or "", 
        telefono=telefono or "", 
        direccion=direccion or "", 
        user_id=current_user.id
    )
    db.add(db_client)
    db.commit()
    
    return RedirectResponse(url="/clients", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/clients/", response_model=schemas.ClientResponse)
def clients_post(client: schemas.ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """API para creación rápida de clientes (JSON)."""
    db_client = Client(
        nombre=client.nombre,
        cedula=client.cedula or "",
        telefono=client.telefono or "",
        direccion=client.direccion or "",
        user_id=current_user.id
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.get("/clients/{client_id}", response_class=HTMLResponse)
def client_detail(request: Request, client_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    client = db.query(Client).options(joinedload(Client.loans).joinedload(Loan.transactions)).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    active_loans = []
    for l in client.loans:
        if l.estatus == 'activo':
            # Calculamos deuda pendiente en USD para mostrar en perfil
            deuda = utils.obtener_deuda_pendiente(l)
            # Si el préstamo original fue en VES, podemos dejar la deuda en reflejo USD para el perfil unificado
            active_loans.append({
                "id": l.id,
                "monto_principal": l.monto_original if l.monto_original else l.monto_principal,
                "moneda": l.moneda,
                "porcentaje_interes": l.porcentaje_interes,
                "fecha_creacion": l.fecha_creacion,
                "deuda_pendiente": deuda
            })
            
    total_deuda = sum(l['deuda_pendiente'] for l in active_loans)
            
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("detalle-cliente.html", {
        "request": request,
        "client": client,
        "active_loans": active_loans,
        "total_deuda": total_deuda,
        "unread_count": unread_count,
        "format_currency": format_currency # Fix reference to local func
    })

@app.get("/loans/new", response_class=HTMLResponse)
def new_loan_get(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    tasa_actual = update_bcv_rate_if_needed(db)
    clients = db.query(Client).filter(Client.user_id == current_user.id).all()
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    csrf_token = generate_csrf_token()
    return templates.TemplateResponse("formulario-de-prestamo.html", {"request": request, "tasa_actual": tasa_actual, "clients": clients, "unread_count": unread_count, "user": current_user, "csrf_token": csrf_token})

@app.post("/loans/new")
def new_loan_post(
    client_id: int = Form(...),
    monto_principal: float = Form(...),
    moneda: str = Form(...),
    porcentaje_interes: float = Form(...),
    frecuencia: str = Form("mensual"),
    cuotas: int = Form(1),
    fecha_inicio: str = Form(None),
    fecha_fin: str = Form(None),
    notas: str = Form(""),
    csrf_token: str = Form(""),
    archivos: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    if not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF Token inválido")
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        return RedirectResponse(url="/loans", status_code=status.HTTP_303_SEE_OTHER)

    tasa = update_bcv_rate_if_needed(db)
    
    # 1. Validar capital y descontar ATÓMICAMENTE
    # Usamos una sola consulta de actualización con filtro de saldo para evitar race conditions
    if moneda == "USD":
        updated = db.query(User).filter(
            User.id == current_user.id,
            User.capital_total_usd >= monto_principal
        ).update({User.capital_total_usd: User.capital_total_usd - monto_principal})
    else:
        updated = db.query(User).filter(
            User.id == current_user.id,
            User.capital_total_ves >= monto_principal
        ).update({User.capital_total_ves: User.capital_total_ves - monto_principal})

    if not updated:
        return RedirectResponse(url="/loans/new?error=capital_insuficiente", status_code=status.HTTP_303_SEE_OTHER)

    # 2. Preparar fechas
    try:
        start_date = datetime.strptime(fecha_inicio, "%Y-%m-%d").date() if fecha_inicio else datetime.utcnow().date()
        end_date = datetime.strptime(fecha_fin, "%Y-%m-%d").date() if fecha_fin else None
    except:
        start_date = datetime.utcnow().date()
        end_date = None

    # 3. Calcular montos base
    monto_base_db = monto_principal / tasa if moneda == "VES" else monto_principal

    # 4. Crear préstamo
    new_loan = Loan(
        client_id=client_id,
        monto_principal=monto_base_db,
        monto_original=monto_principal,
        moneda=moneda,
        porcentaje_interes=porcentaje_interes,
        tasa_bcv_snapshot=tasa,
        frecuencia_pagos=frecuencia,
        cuotas_totales=max(1, cuotas),
        fecha_inicio=start_date,
        fecha_vencimiento=end_date,
        notas=notas,
        estatus='activo'
    )
    db.add(new_loan)
    db.flush() # Para obtener el ID antes del commit
    
    # 5. Manejar subida de archivos con validación básica
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.docx'}
    MAX_FILE_SIZE = 5 * 1024 * 1024 # 5MB

    for upload_file in archivos:
        if upload_file.filename:
            ext = os.path.splitext(upload_file.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue # Opcional: lanzar error
            
            # Validar tamaño (requiere leer o chequear el descriptor)
            unique_filename = f"loan_{new_loan.id}_{int(datetime.now().timestamp())}{ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            
            attachment = LoanAttachment(loan_id=new_loan.id, file_path=f"/static/uploads/{unique_filename}")
            db.add(attachment)
    
    # 6. Registrar transacciones y finalizar
    monto_usd_egreso = monto_principal if moneda == "USD" else monto_base_db
    egreso_trans = Transaction(
        loan_id=new_loan.id,
        tipo='egreso_capital',
        monto=monto_usd_egreso,
        monto_real=monto_principal,
        moneda=moneda
    )
    db.add(egreso_trans)
    db.commit()

    crear_alerta(db, current_user.id, "Préstamo Otorgado", f"Préstamo registrado para {client.nombre}.", "success")
    return RedirectResponse(url="/loans", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/loans/{loan_id}", response_class=HTMLResponse)
def loan_detail(request: Request, loan_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    loan = db.query(Loan).join(Client).filter(Loan.id == loan_id, Client.user_id == current_user.id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    
    tasa_actual = update_bcv_rate_if_needed(db)
    deuda_pendiente = utils.obtener_deuda_pendiente(loan)
    
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("detalle-prestamo.html", {
        "request": request,
        "loan": loan,
        "tasa_actual": tasa_actual,
        "deuda_pendiente": deuda_pendiente,
        "unread_count": unread_count
    })

@app.get("/clients/{client_id}/edit", response_class=HTMLResponse)
def edit_client_get(request: Request, client_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("editar-cliente.html", {"request": request, "client": client, "unread_count": unread_count})

@app.post("/clients/{client_id}/edit")
def edit_client_post(
    client_id: int,
    nombre: str = Form(...),
    cedula: str = Form(None),
    telefono: str = Form(None),
    direccion: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    client.nombre = nombre
    client.cedula = cedula or ""
    client.telefono = telefono or ""
    client.direccion = direccion or ""
    db.commit()
    
    crear_alerta(db, current_user.id, "Cliente Actualizado", f"Los datos de {nombre} han sido modificados.", "info")
    return RedirectResponse(url=f"/clients/{client_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/clients/{client_id}/delete")
def delete_client(client_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Optional: Check if tiene préstamos activos? User said "repara las funciones", let's just let them delete.
    db.delete(client)
    db.commit()
    
    crear_alerta(db, current_user.id, "Cliente Eliminado", f"Se ha borrado el registro del cliente.", "alert")
    return RedirectResponse(url="/clients", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/settings/capital", response_class=HTMLResponse)
def capital_settings_get(request: Request, current_user: User = Depends(require_user)):
    """Muestra formulario para configurar capital."""
    return templates.TemplateResponse("capital_settings.html", {"request": request, "user": current_user})

@app.post("/settings/capital")
def capital_settings_post(
    capital_usd: float = Form(None), 
    capital_ves: float = Form(None), 
    ajuste_usd: float = Form(0.0),
    ajuste_ves: float = Form(0.0),
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_user)
):
    user = current_user
    if user:
        # Ajustes relativos (Suma/Resta) - Operaciones ATÓMICAS en el motor SQL
        if ajuste_usd != 0:
            db.query(User).filter(User.id == user.id).update({
                User.capital_total_usd: User.capital_total_usd + ajuste_usd
            })
            ct = CapitalTransaction(user_id=user.id, tipo="inversion" if ajuste_usd > 0 else "retiro", monto=abs(ajuste_usd), moneda="USD")
            db.add(ct)
        
        if ajuste_ves != 0:
            db.query(User).filter(User.id == user.id).update({
                User.capital_total_ves: User.capital_total_ves + ajuste_ves
            })
            ct = CapitalTransaction(user_id=user.id, tipo="inversion" if ajuste_ves > 0 else "retiro", monto=abs(ajuste_ves), moneda="VES")
            db.add(ct)

        # Ajustes directos (si se enviaron valores en los inputs de "Total")
        if capital_usd is not None and ajuste_usd == 0:
            dif_usd = capital_usd - user.capital_total_usd
            if dif_usd != 0:
                ct = CapitalTransaction(user_id=user.id, tipo="ajuste_directo", monto=abs(dif_usd), moneda="USD")
                db.add(ct)
                user.capital_total_usd = capital_usd
        
        if capital_ves is not None and ajuste_ves == 0:
            dif_ves = capital_ves - user.capital_total_ves
            if dif_ves != 0:
                ct = CapitalTransaction(user_id=user.id, tipo="ajuste_directo", monto=abs(dif_ves), moneda="VES")
                db.add(ct)
                user.capital_total_ves = capital_ves
        
        # Generar notificación silenciosa (Audit trail)
        if ajuste_usd != 0 or ajuste_ves != 0 or capital_usd is not None or capital_ves is not None:
            crear_alerta(db, user.id, "Capital Actualizado", "Tus ajustes de capital han sido guardados.", "success")
            
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/settings/profile", response_class=HTMLResponse)
def profile_settings_get(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    tasa_actual = update_bcv_rate_if_needed(db)
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("perfil-usuario.html", {
        "request": request, 
        "user": current_user, 
        "unread_count": unread_count,
        "tasa_actual": tasa_actual,
        "vapid_public_key": VAPID_PUBLIC_KEY
    })

@app.post("/settings/profile")
def profile_settings_post(
    nombre: str = Form(""),
    apellido: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    current_user.nombre = nombre.strip()
    current_user.apellido = apellido.strip()
    if password:
        current_user.hashed_password = hash_password(password)
    db.commit()
    return RedirectResponse(url="/settings/profile?saved=1", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/loans/{loan_id}/cancel")
def cancel_loan(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    """Anula un préstamo activo y devuelve el capital al usuario."""
    loan = db.query(Loan).join(Client).filter(Loan.id == loan_id, Client.user_id == current_user.id).first()
    if not loan or loan.estatus != 'activo':
        raise HTTPException(status_code=404, detail="Préstamo no encontrado o ya no está activo")
    
    # Devolver el capital pendiente real (Principal original - Pagos realizados a principal)
    pagos_usd = sum(t.monto for t in loan.transactions if t.tipo == 'pago_cuota')
    capital_por_recuperar = max(0.0, loan.monto_principal - pagos_usd)
    
    if loan.moneda == "USD":
        db.query(User).filter(User.id == current_user.id).update({User.capital_total_usd: User.capital_total_usd + capital_por_recuperar})
    else:
        tasa = update_bcv_rate_if_needed(db)
        db.query(User).filter(User.id == current_user.id).update({User.capital_total_ves: User.capital_total_ves + (capital_por_recuperar * tasa)})
    
    loan.estatus = 'anulado'
    
    # Registrar devolución de capital (Anulación)
    reintegro_trans = Transaction(
        loan_id=loan.id,
        tipo='ingreso_extra',  # Ahora es legítimo para auditoría de anulaciones
        monto=capital_por_recuperar,
        monto_real=capital_por_recuperar if loan.moneda == "USD" else (capital_por_recuperar * update_bcv_rate_if_needed(db)),
        moneda=loan.moneda
    )
    db.add(reintegro_trans)
    
    db.commit()
    crear_alerta(db, current_user.id, "Préstamo Anulado", f"El préstamo de {loan.client.nombre} fue anulado. Capital devuelto al fondo.", "alert")
    return RedirectResponse(url="/loans", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/notifications", response_class=HTMLResponse)
def notifications_view(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    notifs = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.fecha.desc()).all()
    unread_count = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.leida == False).count()
    return templates.TemplateResponse("notificaciones.html", {"request": request, "notifications": notifs, "unread_count": unread_count})

@app.post("/notifications/read-all")
def notifications_read_all(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    db.query(Notification).filter(Notification.user_id == current_user.id).update({"leida": True})
    db.commit()
    return RedirectResponse(url="/notifications", status_code=status.HTTP_303_SEE_OTHER)

# --- Pagos ---
@app.post("/loans/{loan_id}/pay")
def register_payment(
    loan_id: int,
    monto: float = Form(...),
    moneda_pago: str = Form("USD"),
    tasa_pago: float = Form(None),
    tipo: str = Form("pago_cuota"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user)
):
    loan = db.query(Loan).join(Client).filter(Loan.id == loan_id, Client.user_id == current_user.id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
        
    if monto <= 0:
        # Retornar error amistoso en la UI en vez de 400 seco (prevenir robo de capital por saldo negativo)
        return RedirectResponse(url="/loans", status_code=status.HTTP_303_SEE_OTHER)
    
    # Nueva Lógica de Indexación (VES -> USD interno)
    tasa = tasa_pago or update_bcv_rate_if_needed(db)
    monto_final_usd = monto
    
    if loan.moneda == "VES":
        # Todo se reduce en base USD interno
        if moneda_pago == "VES":
            monto_final_usd = monto / tasa
        else:
            monto_final_usd = monto # Ya viene en USD
    else:
        # Préstamo en USD puro
        if moneda_pago == "VES":
            monto_final_usd = monto / tasa
        else:
            monto_final_usd = monto

    # Registrar la transacción
    new_transaction = Transaction(
        loan_id=loan_id, 
        tipo=tipo, 
        monto=monto_final_usd, 
        monto_real=monto, 
        moneda=moneda_pago
    )
    db.add(new_transaction)
    
    # Aumentar capital del usuario - ATÓMICAMENTE en SQL
    if moneda_pago == "USD":
        db.query(User).filter(User.id == current_user.id).update({
            User.capital_total_usd: User.capital_total_usd + monto
        })
    else:
        db.query(User).filter(User.id == current_user.id).update({
            User.capital_total_ves: User.capital_total_ves + monto
        })

    db.commit()
    db.refresh(loan)
    
    # Calculamos la deuda pendiente para alertas, en la moneda del préstamo
    deuda = utils.obtener_deuda_pendiente(loan, en_bolivares=True, tasa_actual=tasa)
    
    if deuda <= 0.5: # Margen por redondeo en VES/USD
        loan.estatus = 'pagado'
        crear_alerta(db, current_user.id, "Préstamo Liquidado", f"El préstamo de {loan.client.nombre} ha sido pagado totalmente.", "success")
    else:
        crear_alerta(db, current_user.id, "Abono Recibido", f"Se registró un pago de {monto} {moneda_pago} de {loan.client.nombre}.", "info")
        
    db.commit()
    return RedirectResponse(url="/loans", status_code=status.HTTP_303_SEE_OTHER)

# --- APIs de ejemplo para probar desde un cliente ---
@app.post("/clients/", response_model=schemas.ClientResponse)
def create_client(
    request: Request,
    client: schemas.ClientCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_user)
):
    """Registrar un nuevo cliente vía API."""
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token or not verify_csrf_token(csrf_token):
        raise HTTPException(status_code=403, detail="CSRF Token inválido")
        
    db_client = Client(**client.model_dump(), user_id=current_user.id)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.post("/loans/", response_model=schemas.LoanResponse)
def create_loan(loan: schemas.LoanCreate, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Crear un préstamo y snapshot de la tasa del día."""
    # Verificar que el cliente pertenezca al usuario actual
    client = db.query(Client).filter(Client.id == loan.client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=403, detail="No autorizado para este cliente")
        
    tasa = update_bcv_rate_if_needed(db)
    
    db_loan = Loan(
        **loan.model_dump(),
        tasa_bcv_snapshot=tasa,
        estatus='activo'
    )
    db.add(db_loan)
    db.commit()
    db.refresh(db_loan)
    return db_loan

@app.get("/reports", response_class=HTMLResponse)
def reports_dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Dashboard de Reportes y Analíticas."""
    user = current_user
    tasa_actual = update_bcv_rate_if_needed(db)

    active_loans = db.query(Loan).options(joinedload(Loan.transactions), joinedload(Loan.client)).join(Client).filter(Client.user_id == current_user.id, Loan.estatus == 'activo').all()

    prestamos_vencidos = sum(1 for l in active_loans if utils.chequear_cuota_vencida(l))
    total_activos = len(active_loans)
    capital_prestado_usd = sum(max(0.0, l.monto_principal - sum(t.monto for t in l.transactions if t.tipo == 'pago_cuota')) for l in active_loans)

    ganancias_proyectadas = sum(
        utils.calcular_interes_simple(l.monto_principal, l.porcentaje_interes) * (l.cuotas_totales or 1)
        for l in active_loans
    )

    ganancias_reales = 0.0
    all_user_loans = db.query(Loan).join(Client).filter(Client.user_id == user.id).all()
    for l in all_user_loans:
        pagos_usd = sum(t.monto for t in l.transactions if t.tipo == 'pago_cuota')
        if pagos_usd > l.monto_principal:
            ganancias_reales += (pagos_usd - l.monto_principal)

    unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.leida == False).count()

    disponible_usd = user.capital_total_usd
    disponible_ves = user.capital_total_ves

    # Gráfico mensual (últimos 7 meses)
    meses_labels = []
    meses_valores = []
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    hoy = datetime.utcnow()

    current_month = datetime(hoy.year, hoy.month, 1)

    for i in range(6, -1, -1):
        target_m = current_month.month - i - 1
        target_y = current_month.year + (target_m // 12)
        target_m = (target_m % 12) + 1
        
        mes_label = meses_nombres[target_m - 1]
        meses_labels.append(mes_label)
        start = datetime(target_y, target_m, 1)
        if target_m == 12:
            end = datetime(target_y + 1, 1, 1)
        else:
            end = datetime(target_y, target_m + 1, 1)
        sum_mes = db.query(func.sum(Transaction.monto)).join(Loan).join(Client).filter(
            Client.user_id == user.id,
            Transaction.tipo == 'pago_cuota',
            Transaction.fecha >= start,
            Transaction.fecha < end
        ).scalar() or 0
        meses_valores.append(sum_mes)

    max_val = max(meses_valores) if meses_valores and max(meses_valores) > 0 else 1
    grafico_data = [{"label": l, "height": int((v / max_val) * 100)} for l, v in zip(meses_labels, meses_valores)]

    # Listado de préstamos activos con campo vencido
    loans_activos = []
    for l in active_loans:
        loans_activos.append({
            "id": l.id,
            "client": l.client,
            "monto_principal": l.monto_original if l.monto_original else l.monto_principal,
            "moneda": l.moneda,
            "porcentaje_interes": l.porcentaje_interes,
            "fecha_creacion": l.fecha_creacion,
            "fecha_vencimiento": l.fecha_vencimiento,
            "vencido": utils.chequear_cuota_vencida(l),
        })

    # Estadísticas extra
    promedio_prestamo = (capital_prestado_usd / total_activos) if total_activos > 0 else 0
    recaudacion_total = db.query(func.sum(Transaction.monto)).join(Loan).join(Client).filter(
        Client.user_id == user.id,
        Transaction.tipo == 'pago_cuota'
    ).scalar() or 0
    
    usd_count = sum(1 for l in active_loans if l.moneda == 'USD')
    ves_count = sum(1 for l in active_loans if l.moneda == 'VES')

    return templates.TemplateResponse("reportes-dashboard.html", {
        "request": request,
        "user": user,
        "total_activos": total_activos,
        "prestamos_vencidos": prestamos_vencidos,
        "capital_prestado_usd": capital_prestado_usd,
        "ganancias_reales": ganancias_reales,
        "ganancias_proyectadas": ganancias_proyectadas,
        "disponible_usd": disponible_usd,
        "disponible_ves": disponible_ves,
        "tasa_actual": tasa_actual,
        "grafico_data": grafico_data,
        "loans_activos": loans_activos,
        "unread_count": unread_count,
        "promedio_prestamo": promedio_prestamo,
        "recaudacion_total": recaudacion_total,
        "usd_count": usd_count,
        "ves_count": ves_count
    })


