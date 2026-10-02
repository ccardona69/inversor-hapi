"""Marcador de bolsillo (Fase 1): lo que salió del bolsillo, lo que vale hoy y
el fantasma S&P 500 con retorno total. Módulo puro: sin base de datos ni red.

Reglas del plan:
- El costo del depósito usa el tipo de cambio de mercado del día (fuente
  externa con fecha), jamás el implícito soles/usd de la fila, que siempre
  daría costo 0. `fx_rate` se guarda en la tabla solo como dato.
- El fantasma y la cartera real parten del mismo `depositado_neto`: el costo
  del depósito lo pagan ambos; no hay asimetría que ajustar.
- Solo se suman los costos de depósito: las comisiones de operación ya vienen
  netas en los montos de Hapi; dividendos y ahorro_soles no cuentan aquí.
"""
import math

SETTINGS_DEFAULTS = {
    "deposit_fee": 3.0,              # costo estimado por depósito en USD, editable
    "r": 0.05,                       # costo anual de oportunidad del dinero quieto
    "fx_default": 3.55,              # soles por dólar de referencia para la alcancía
    "etf_target_pct": 50,            # piso de ETF en la cartera (regla del plan)
    "etf_plan": "SPY",               # ETF del plan: destino de aportes y fantasma
    "w8ben_expiry": None,            # vencimiento del W-8BEN (YYYY-MM-DD)
    "last_hapi_check": None,         # última entrada a Hapi (actividad = login)
    "ahorro_mensual_declarado": 80,  # ESTIMACIÓN mientras haya <2 meses de datos
}

ETF_TICKERS = frozenset(
    "SPY VOO IVV SPLG VTI ITOT SCHB SCHX QQQ QQQM VT ACWI VEA VXUS IWM DIA RSP".split())

# Meta del plan = índices amplios que sí diversifican una cartera concentrada
# en megacaps. QQQ/QQQM (100 Nasdaq, con AMZN y GOOG dentro) y DIA (30 valores)
# no la cumplen: con ellos se «alcanzaría la meta» sin diversificar.
ETF_META = frozenset(
    "SPY VOO IVV SPLG VTI ITOT SCHB SCHX VT ACWI VEA VXUS IWM RSP".split())

NOTAS_FANTASMA = [
    "La diferencia incluye lo que te costó operar más veces que el índice.",
    "Incluye la retención del 30 % sobre dividendos del índice, estimada con close/adjclose.",
]


def normalize_tc(value):
    """Acepta USD/PEN (~3.55) o su inverso PEN/USD (~0.28) y devuelve soles por
    dólar solo si cae en el rango razonable 2.5–5. Fuera de rango → None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        tc = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(tc):
        return None
    if 0 < tc < 1:
        tc = 1 / tc
    return tc if 2.5 <= tc <= 5 else None


def etf_meta_value(posiciones):
    """USD en ETF de índice amplio VERIFICADOS (numerador de etf_pct):
    un ETF sin verificar no puede aflojar la regla del plan."""
    return round(sum((p.get("market_value") or 0) for p in posiciones
                     if p.get("verified") and p.get("ticker") in ETF_META), 2)


def etf_pct(posiciones):
    """% de ETF de índice amplio sobre la exposición con precio.

    Fail-closed en ambos sentidos: el denominador cuenta TODAS las posiciones
    con precio (una acción sin verificar no puede inflar el %), y el numerador
    solo ETF verificados (uno sin verificar no puede aflojar la regla).
    None si nada tiene precio."""
    total = sum(p.get("market_value") or 0 for p in posiciones
                if p.get("market_value") is not None)
    if not total:
        return None
    return round(etf_meta_value(posiciones) / total * 100, 2)


def depositado_neto(rows):
    """Σ depósitos − Σ retiros, en USD. ahorro_soles y dividendos no cuentan."""
    neto = 0.0
    for row in rows:
        usd = row.get("amount_usd") or 0
        if row.get("kind") == "deposito":
            neto += usd
        elif row.get("kind") == "retiro":
            neto -= usd
    return round(neto, 2)


def costo_deposito(row, tc_ref, deposit_fee):
    """Costo del depósito: soles_enviados / tc_mercado − usd_llegados.

    Solo CÁLCULO cuando la fila trae soles+usd Y hay tc de mercado normalizado;
    con cualquier dato faltante se estima con la tarifa configurada (nunca con
    el tipo de cambio implícito, que haría el costo 0 por construcción)."""
    soles, usd = row.get("soles_amount"), row.get("amount_usd")
    if soles and usd and tc_ref:
        valor = round(soles / tc_ref - usd, 2)
        return {"valor": valor, "etiqueta": "CÁLCULO",
                "detalle": f"S/ {soles:g} ÷ tc {tc_ref:g} − $ {usd:g}"}
    return {"valor": round(deposit_fee, 2), "etiqueta": "ESTIMACIÓN",
            "detalle": f"tarifa estimada de depósito $ {deposit_fee:g}"}


def marcador(rows, valor_actual, deposit_fee, tc_lookup=None):
    """Resultado de bolsillo. `tc_lookup(fecha)` devuelve (tc, fuente, fecha)
    del mercado ese día o el día hábil anterior, o None si no hay dato."""
    depositos = [r for r in rows if r.get("kind") == "deposito"]
    neto = depositado_neto(rows)
    detalle, estimado = [], False
    for row in depositos:
        tc = fuente = fecha_tc = None
        if tc_lookup is not None:
            try:
                hit = tc_lookup((row.get("at") or "")[:10])
            except Exception:
                hit = None
            if hit:
                tc, fuente, fecha_tc = hit
        costo = costo_deposito(row, tc, deposit_fee)
        estimado = estimado or costo["etiqueta"] == "ESTIMACIÓN"
        detalle.append({"at": row.get("at"), "amount_usd": row.get("amount_usd"),
                        "soles_amount": row.get("soles_amount"), **costo,
                        "tc_ref": tc, "tc_fuente": fuente, "tc_fecha": fecha_tc})
    costos = round(sum(d["valor"] for d in detalle), 2)
    puesto = round(neto + costos, 2)
    resultado = round(valor_actual - puesto, 2) if valor_actual is not None else None
    pct = (round(resultado / puesto * 100, 2)
           if resultado is not None and puesto > 0 else None)
    return {"depositado_neto": neto, "n_depositos": len(depositos),
            "costos_deposito": costos,
            "costos_etiqueta": "ESTIMACIÓN" if estimado else "CÁLCULO",
            "costos_detalle": detalle,
            "puesto_bolsillo": puesto, "valor_actual": valor_actual,
            "resultado_real": resultado, "resultado_pct": pct}


def fantasma_spy(rows, spy_rows, fee_per_buy=0.15, withholding=0.30):
    """El mismo dinero si cada depósito neto hubiera comprado SPY al cierre de
    su fecha (o el primer día hábil posterior), con retorno total menos la
    retención del 30 % sobre dividendos que paga un no residente.

    La componente de dividendos por tramo se estima comparando adjclose con
    close: retorno_neto ≈ retorno_precio + (1−withholding)·(retorno_total −
    retorno_precio). Cada compra descuenta `fee_per_buy`. Si falta la serie,
    falta close/adjclose o algún movimiento no tiene precio en/después de su
    fecha → None ("sin dato"): el fantasma no se inventa."""
    series = sorted((r for r in (spy_rows or [])
                     if r.get("date") and r.get("adjclose") is not None
                     and r.get("close") is not None and r["close"]),
                    key=lambda r: r["date"])
    if not series:
        return None
    last = series[-1]
    valor = acciones = 0.0
    for mov in rows:
        if mov.get("kind") not in ("deposito", "retiro"):
            continue
        usd = mov.get("amount_usd")
        fecha = (mov.get("at") or "")[:10]
        px = next((r for r in series if r["date"] >= fecha), None)
        if not usd or usd <= 0 or px is None:
            return None
        total_ret = last["adjclose"] / px["adjclose"] - 1
        precio_ret = last["close"] / px["close"] - 1
        neto_ret = precio_ret + (1 - withholding) * (total_ret - precio_ret)
        if mov["kind"] == "deposito":
            valor += (usd - fee_per_buy) * (1 + neto_ret)
            acciones += (usd - fee_per_buy) / px["close"]
        else:
            valor -= usd * (1 + neto_ret)
            acciones -= usd / px["close"]
    return {"valor_fantasma": round(valor, 2),
            "acciones_fantasma": round(acciones, 6),
            "fecha_precio": last["date"], "notas": list(NOTAS_FANTASMA)}
