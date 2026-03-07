import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

# URL de la base de datos (Usa variable de entorno para la nube o SQLite local por defecto)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./loans.db")

# Si la URL empieza con postgres:// (como en Render/Neon), cambiarla a postgresql:// para SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuración del motor
if DATABASE_URL.startswith("sqlite"):
    print("DATABASE: Usando SQLite local.")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    print(f"DATABASE: Conectando a {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'remoto'}")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) 
    nombre = Column(String, nullable=True)
    apellido = Column(String, nullable=True)
    hashed_password = Column(String)
    capital_total_usd = Column(Float, default=0.0)
    capital_total_ves = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    webauthn_id = Column(String, unique=True, nullable=True) # Unico para cada usuario
    
    credentials = relationship("WebAuthnCredential", back_populates="user")
    push_subscriptions = relationship("PushSubscription", back_populates="user")

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    nombre = Column(String, index=True)
    telefono = Column(String)
    cedula = Column(String, nullable=True)
    direccion = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="clients")
    loans = relationship("Loan", back_populates="client")

class Rate(Base):
    __tablename__ = "rates"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, unique=True, index=True)
    valor_bs_bcv = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    monto_principal = Column(Float) 
    monto_original = Column(Float, nullable=True) 
    moneda = Column(String) # 'USD' o 'VES'
    tasa_bcv_snapshot = Column(Float)
    porcentaje_interes = Column(Float)
    frecuencia_pagos = Column(String, default="mensual") 
    cuotas_totales = Column(Integer, default=1)
    fecha_inicio = Column(Date, default=datetime.utcnow().date)
    fecha_vencimiento = Column(Date, nullable=True)
    estatus = Column(String, default="activo") 
    notas = Column(String, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    client = relationship("Client", back_populates="loans")
    transactions = relationship("Transaction", back_populates="loan")
    attachments = relationship("LoanAttachment", back_populates="loan")

class LoanAttachment(Base):
    __tablename__ = "loan_attachments"
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"))
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    loan = relationship("Loan", back_populates="attachments")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"))
    tipo = Column(String) 
    monto = Column(Float) 
    monto_real = Column(Float, nullable=True) 
    moneda = Column(String, default="USD") 
    fecha = Column(DateTime, default=datetime.utcnow)
    
    loan = relationship("Loan", back_populates="transactions")

class CapitalTransaction(Base):
    __tablename__ = "capital_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tipo = Column(String) 
    monto = Column(Float)
    moneda = Column(String, default="USD") 
    fecha = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="capital_transactions")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    titulo = Column(String)
    mensaje = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow)
    tipo = Column(String, default="info") 
    leida = Column(Boolean, default=False)
    
    user = relationship("User", backref="notifications")

class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    credential_id = Column(String, unique=True, index=True)
    public_key = Column(String)
    sign_count = Column(Integer, default=0)
    transports = Column(String, nullable=True) 
    
    user = relationship("User", back_populates="credentials")

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    endpoint = Column(String, unique=True, index=True)
    auth_key = Column(String)
    p256dh_key = Column(String)
    browser = Column(String, nullable=True) # Para saber si es iPhone, Chrome, etc
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="push_subscriptions")

def init_db():
    if os.environ.get("RESET_DATABASE") == "true":
        print("DATABASE: Reseteando base de datos (RESET_DATABASE=true)...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
