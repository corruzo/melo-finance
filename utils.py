from database import Loan, Transaction
from datetime import datetime

def calcular_interes_simple(monto: float, porcentaje: float) -> float:
    return monto * (porcentaje / 100.0)



def chequear_cuota_vencida(loan: Loan) -> bool:
    """Determina si el préstamo tiene una cuota vencida según su frecuencia, contemplando pagos."""
    if loan.estatus in ["pagado", "anulado"]:
        return False
    
    frecuencia_a_dias = {
        "diario": 1,
        "semanal": 7,
        "quincenal": 15,
        "mensual": 30,
    }
    dias_por_periodo = frecuencia_a_dias.get(loan.frecuencia_pagos or "mensual", 30)
    
    dias_transcurridos = (datetime.utcnow() - loan.fecha_creacion).days
    periodos_transcurridos = dias_transcurridos // dias_por_periodo
    
    if periodos_transcurridos == 0:
        return False
        
    # Calcular deuda que debería estar pagada a la fecha
    interes = calcular_interes_simple(loan.monto_principal, loan.porcentaje_interes)
    deuda_total_usd = loan.monto_principal + (interes * (loan.cuotas_totales or 1))
    monto_por_cuota = deuda_total_usd / max(1, loan.cuotas_totales)
    
    # Exigir solo hasta el máximo de cuotas pactadas
    cuotas_exigibles = min(max(1, loan.cuotas_totales), periodos_transcurridos)
    deuda_exigible = cuotas_exigibles * monto_por_cuota
    
    pagos_realizados = sum(t.monto for t in loan.transactions if t.tipo == 'pago_cuota')
    
    # Si los pagos cubren la deuda exigible (tolerancia de 1$), no está vencido
    if pagos_realizados >= (deuda_exigible - 1.0):
        # Hay un caso especial: si el préstamo venció por completo en base a fecha
        if loan.fecha_vencimiento and datetime.utcnow().date() > loan.fecha_vencimiento:
            if pagos_realizados < (deuda_total_usd - 1.0):
                return True
        return False
        
    return True

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
