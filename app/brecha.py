"""Brecha del plan ETF y regla del plan (Fase 1 «Brecha y cumplimiento»).

Módulo puro: sin base de datos ni red. Aquí vive la fuente única de la regla
del plan — con el ETF bajo su meta, el próximo dinero va al ETF — que usan el
guard del chat (ai_assistant.plan_guard), trade_check y GET /api/brecha.

Fail-closed por diseño: sin dato de exposición, la regla cuenta como bajo la
meta (igual que el guard original del chat). Todo monto en USD; meta_pct es
porcentaje (50 = 50 %). Las proyecciones son siempre ESTIMACIÓN: precios
constantes, sin ventas ni comisiones.
"""
import math

from .scoreboard import ETF_META, ETF_TICKERS


def es_etf(ticker, etf_tickers=ETF_TICKERS):
    return ticker is not None and str(ticker).upper() in etf_tickers


def _etf_pct(valor_etf, valor_base):
    if valor_base is None or valor_base <= 0 or valor_etf is None:
        return None
    return round(valor_etf / valor_base * 100, 2)


def regla_plan(*, tickers=(), lado, meta_pct, etf_pct=None, valor_etf=None,
               valor_base=None, monto_usd=None, delta_base=None,
               etf_tickers=ETF_META):
    """Regla del plan, fuente única.

    Por defecto solo los ETF de índice amplio (ETF_META) cuentan para la
    meta: comprar QQQ o DIA se evalúa como compra de acción porque no
    diversifica una cartera ya concentrada en megacaps.

    - Compra fuera de etf_tickers: R1 (sin monto) cumple solo si el ETF ya está
      en su meta; R1′ (con monto) exige etf_pct_despues ≥ meta — una compra de
      acciones nunca sube el % de ETF.
    - Compra de ETF y venta de acciones: siempre cumplen (aplica=False).
    - Venta de ETF que deja bajo la meta: cumple pero con aviso.
    - delta_base: lo que la operación suma a la base (compra=+monto,
      venta=−monto); default ±monto_usd según lado.
    """
    res = {"aplica": False, "regla": None, "etf_pct_antes": None,
           "etf_pct_despues": None, "meta_pct": meta_pct, "cumple": True,
           "aviso": None, "motivo": None, "margen_acciones_usd": None}
    if meta_pct is None:
        return res
    antes = etf_pct if etf_pct is not None else _etf_pct(valor_etf, valor_base)
    res["etf_pct_antes"] = antes
    if valor_etf is not None and valor_base is not None and meta_pct > 0:
        res["margen_acciones_usd"] = round(
            max(0.0, valor_etf / (meta_pct / 100) - valor_base), 2)
    toca_etf = any(es_etf(t, etf_tickers) for t in tickers or ())
    en_meta = antes is not None and antes >= meta_pct
    if lado == "comprar" and not toca_etf:
        res["aplica"] = True
        if monto_usd is not None:
            res["regla"] = "R1'"
            if valor_base is not None:
                d = delta_base if delta_base is not None else monto_usd
                res["etf_pct_despues"] = _etf_pct(valor_etf, valor_base + d)
            res["cumple"] = (res["etf_pct_despues"] is not None
                             and res["etf_pct_despues"] + 1e-9 >= meta_pct)
        else:
            res["regla"] = "R1"
            res["cumple"] = en_meta
        if not res["cumple"]:
            res["motivo"] = "etf_bajo_meta"
    elif lado == "vender" and toca_etf:
        res["aplica"] = True
        res["regla"] = "R1'"
        if monto_usd is not None and valor_base is not None and valor_etf is not None:
            d = abs(delta_base) if delta_base is not None else monto_usd
            res["etf_pct_despues"] = _etf_pct(valor_etf - monto_usd, valor_base - d)
            if res["etf_pct_despues"] is not None and res["etf_pct_despues"] < meta_pct:
                res["aviso"] = ("Vender ETF te deja bajo la meta del plan: la "
                                "regla manda el próximo dinero al ETF.")
    return res


def brecha(*, valor_base, valor_etf, meta_pct, a_invertir_usd=0.0, entra_a_base=None):
    """Cuánto del dinero a invertir debe ir al ETF para acercarse a la meta.

    entra_a_base: USD que la inversión suma a la base (default: todo). Con la
    base = posiciones (V-1), el efectivo y el aporte nuevo entran completos
    al invertirse.

    brecha_usd es lo que habría que VENDER de acciones para rebalancear hoy;
    dinero_nuevo_para_meta_usd es lo que hace falta en APORTES para llegar
    sin vender: cada USD nuevo sube el numerador pero también la base, así que
    cierra (1−t) — con meta 50 % hace falta el doble de la brecha."""
    t = (meta_pct or 0) / 100
    B = valor_base or 0.0
    E = valor_etf or 0.0
    D = a_invertir_usd or 0.0
    dB = entra_a_base if entra_a_base is not None else D
    x_estrella = t * (B + dB) - E            # USD a ETF para quedar justo en meta
    a_etf = min(D, max(0.0, x_estrella))
    etf_pct = _etf_pct(E, B)
    brecha_usd = round(max(0.0, t * B - E), 2)
    nuevo = round(brecha_usd / (1 - t), 2) if 0 < t < 1 else None
    return {"meta_pct": meta_pct, "etf_pct": etf_pct,
            "brecha_usd": brecha_usd,
            "dinero_nuevo_para_meta_usd": nuevo,
            "en_meta": etf_pct is not None and etf_pct >= meta_pct,
            "a_invertir_usd": round(D, 2), "a_etf_usd": round(a_etf, 2),
            "libre_usd": round(D - a_etf, 2),
            "brecha_despues_usd": round(max(0.0, x_estrella - D), 2),
            "etf_pct_despues": _etf_pct(E + a_etf, B + dB),
            "margen_acciones_usd": (round(max(0.0, E / t - B), 2) if t > 0 else None)}


def proyeccion(*, brecha_usd, meta_pct, aporte_tipico_usd, meses_por_deposito,
               aporte_alternativo_usd=None):
    """Las tres rutas para cerrar la brecha, sin preseleccionar ninguna.

    Cada aporte que va íntegro al ETF cierra a·(1−t): el depósito sube E pero
    también la base (y con ella la meta). meta_pct=100 hace imposible llegar
    por aportes. 'rebalancear' ignora comisiones y el efecto fiscal (dato
    faltante — se declara)."""
    t = (meta_pct or 0) / 100

    def _ruta(aporte):
        if aporte is None or aporte <= 0 or not 0 < t < 1:
            return None
        n = math.ceil(max(0.0, brecha_usd) / (aporte * (1 - t)))
        return {"aportes": n,
                "meses": round(n * meses_por_deposito, 1) if meses_por_deposito else None}

    return {"etiqueta": "ESTIMACIÓN",
            "despacio": _ruta(aporte_tipico_usd),
            "ahorrar_mas": _ruta(aporte_alternativo_usd),
            "rebalancear": ({"venta_usd": round(brecha_usd, 2),
                            "nota": "sin comisiones ni efecto fiscal (dato faltante)"}
                           if brecha_usd > 0 else None)}
