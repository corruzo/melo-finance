from database import Loan, Transaction
from datetime import datetime

def calcular_interes_simple(monto: float, porcentaje: float) -> float:
    return monto * (porcentaje / 100.0)



def chequear_cuota_vencida(loan: Loan) -> bool:
    """Determina si el préstamo tiene al menos una cuota vencida según su frecuencia real."""
    if loan.estatus == "pagado" or loan.estatus == "anulado":
        return False
    
    frecuencia_a_dias = {
        "diario": 1,
        "semanal": 7,
        "quincenal": 15,
        "mensual": 30,
    }
    dias_por_periodo = frecuencia_a_dias.get(loan.frecuencia_pagos or "mensual", 30)
    
    dias_transcurridos = (datetime.utcnow() - loan.fecha_creacion).days
    # Hay cuota vencida si han pasado más días que un período sin que el préstamo esté pagado
    return dias_transcurridos > dias_por_periodo

def obtener_deuda_pendiente(loan: Loan, en_bolivares: bool = False, tasa_actual: float = 1.0) -> float:
    # Deuda total = (Principal USD + Interés USD) - Pagos realizados USD
    # Asumimos que monto_principal ya está guardado en USD si se sigue la nueva lógica
    interes = calcular_interes_simple(loan.monto_principal, loan.porcentaje_interes)
    deuda_total_usd = loan.monto_principal + (interes * (loan.cuotas_totales or 1)) # Interés total proyectado
    
    pagos_usd = sum(t.monto for t in loan.transactions if t.tipo == 'pago_cuota')
    deuda_pendiente_usd = max(0.0, deuda_total_usd - pagos_usd)
    
    if en_bolivares and loan.moneda == "VES":
        return deuda_pendiente_usd * tasa_actual
    return deuda_pendiente_usd
