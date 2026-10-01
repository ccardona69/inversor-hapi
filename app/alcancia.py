"""Alcancía (Fase 1): junta varios meses de ahorro en soles antes de depositar
para pagar menos tarifas fijas. EOQ clásico sobre el ahorro anual en USD.
Módulo puro: sin base de datos ni red.

progreso = ahorro declarado en soles − soles ya enviados a Hapi. Al depositar
se descuentan los soles enviados y el sobrante queda dentro (ahorraste S/500,
enviaste S/480 → arrancas con S/20). Con menos de 2 meses de datos de ahorro
se usa el ahorro mensual declarado por el usuario (ESTIMACIÓN).
"""
import math
from datetime import date


def eoq(D_usd, r, F):
    """Número óptimo de depósitos al año: sqrt(r·D / 2F)."""
    return math.sqrt(r * D_usd / (2 * F))


def _fecha(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def plan(rows, r, fee, fx, declarado_mensual, today):
    """Meta práctica de la alcancía en soles a partir de los movimientos.

    Devuelve progreso, cadena de meses y la comparación entre el óptimo exacto
    EOQ y la meta práctica (depósitos enteros al año). Sin datos suficientes de
    ahorro usa `declarado_mensual` y lo marca como ESTIMACIÓN."""
    hoy = _fecha(today) or date.today()
    savings = sum(r2.get("soles_amount") or 0
                  for r2 in rows if r2.get("kind") == "ahorro_soles")
    sent = sum(r2.get("soles_amount") or 0
               for r2 in rows if r2.get("kind") == "deposito")
    progreso = max(0.0, savings - sent)
    fechas = sorted(f for f in (_fecha(r2.get("at")) for r2 in rows
                                if r2.get("kind") == "ahorro_soles") if f)
    meses = (hoy - fechas[0]).days / 30.44 if fechas else 0.0
    if not fechas or meses < 2:
        monthly = float(declarado_mensual or 0)
        estimado = True
    else:
        monthly = savings / meses
        estimado = False

    base = {"progreso": round(progreso, 2), "ahorro_mensual": round(monthly, 2),
            "ahorro_estimado": estimado, "meses_datos": round(meses, 2),
            "ahorrado_soles": round(savings, 2), "enviado_soles": round(sent, 2)}
    if monthly <= 0 or not fx or fx <= 0 or fee <= 0 or r <= 0:
        return {**base, "n_optimo": None, "n_practico": None, "meta_usd": None,
                "meta_soles": None, "optimo_soles": None, "meses_por_deposito": None,
                "faltan_meses": None, "llego_meta": False}

    d_anual = monthly * 12 / fx
    n_optimo = eoq(d_anual, r, fee)
    n_practico = max(1, math.ceil(n_optimo))
    meta_usd = round(d_anual / n_practico, 2)
    meta_soles = round(meta_usd * fx, 2)
    optimo_soles = round(d_anual / n_optimo * fx, 2)
    return {**base,
            "n_optimo": round(n_optimo, 2), "n_practico": n_practico,
            "meta_usd": meta_usd, "meta_soles": meta_soles,
            "optimo_soles": optimo_soles,
            "meses_por_deposito": round(meta_soles / monthly, 1),
            "faltan_meses": math.ceil(max(0.0, meta_soles - progreso) / monthly),
            "llego_meta": progreso >= meta_soles,
            # F (costo por depósito) es una tarifa configurada que mezcla lo
            # fijo con lo proporcional; lo proporcional no depende de la
            # cadencia. Con F sobrestimada, N* subestima los depósitos al año:
            # la cadencia real probablemente sea mayor. Se recalibra cuando
            # lleguen los soles reales del banco (backlog Fase 2).
            "cadencia_estimada": True,
            "cadencia_nota": ("Cadencia orientativa: el costo de depósito "
                              "parece mayormente proporcional al monto y se "
                              "recalibrará con tus soles reales; la cadencia "
                              "óptima probablemente es algo más corta.")}
