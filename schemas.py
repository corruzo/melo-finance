from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# --- schemas para User ---
class UserBase(BaseModel):
    username: str
    capital_total_usd: float = 0.0

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True # Compatibilidad con Pydantic V2

# --- schemas para Client ---
class ClientBase(BaseModel):
    nombre: str
    telefono: str
    cedula: Optional[str] = None
    direccion: str

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: int

    class Config:
        from_attributes = True

# --- schemas para Loan ---
class LoanBase(BaseModel):
    monto_principal: float
    monto_original: Optional[float] = None
    moneda: str = Field(..., description="'USD' o 'VES'")
    porcentaje_interes: float

class LoanCreate(LoanBase):
    client_id: int

class LoanResponse(LoanBase):
    id: int
    client_id: int
    tasa_bcv_snapshot: float
    estatus: str
    fecha_creacion: datetime

    class Config:
        from_attributes = True

# --- schemas para Transaction ---
class TransactionBase(BaseModel):
    tipo: str = Field(..., description="'pago_cuota', 'ingreso_extra'")
    monto: float

class TransactionCreate(TransactionBase):
    loan_id: int

class TransactionResponse(TransactionBase):
    id: int
    loan_id: int
    fecha: datetime

    class Config:
        from_attributes = True
