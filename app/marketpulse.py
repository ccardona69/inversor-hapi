"""Pulso de mercado y niveles operativos por acción.

Todo es regla técnica explícita sobre datos de Yahoo Finance con fecha; no es
predicción ni recomendación. Las cachés en memoria evitan repetir descargas
(pulso 15 min, niveles 10 min) y se limpian con `_clear_cache()` en pruebas.
"""
from datetime import datetime, timezone

from . import marketdata as MD

INSTRUMENTS = [
    ("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Empresas pequeñas"),
    ("^VIX", "VIX (miedo)"), ("USO", "Petróleo"), ("TLT", "Bonos EE.UU. 20 años"), ("GLD", "Oro"),
]
FUENTE = "Yahoo Finance (chart API)"
NOTA = "Regla técnica con datos de mercado; no es predicción ni recomendación."
LECTURA_DIA = {
    "rojo_miedo": "Día rojo con miedo alto: no vendas por pánico ni compres de golpe; escalona y revisa tus stops.",
    "rojo": "Día rojo: suele ser mejor para compras escalonadas que para vender por miedo, si tu tesis sigue válida.",
    "verde": "Día verde fuerte: si una posición está estirada (RSI > 70), es razonable vender una parte.",
    "tranquilo": "Día tranquilo: decide por valoración y tesis, no por el ruido.",
}
PULSE_MAX_AGE_S = 900
PULSE_ERROR_MAX_AGE_S = 60   # sin SPY no se fija el pulso 15 min: se reintenta pronto
LEVELS_MAX_AGE_S = 600

_pulse_cache = {"at": None, "value": None}
_levels_cache = {}


def _clear_cache():
    _pulse_cache.update(at=None, value=None)
    _levels_cache.clear()


def _now(now=None):
    return now or datetime.now(timezone.utc)


def _pct(v):
    return "s/d" if v is None else f"{v:+.1f}%"


def _instrument(ticker, nombre, fetch_quote, fetch_history):
    try:
        q = fetch_quote(ticker)
        item = {"ticker": ticker, "nombre": nombre, "price": q.get("price"),
                "day_change_pct": q.get("day_change_pct"), "asof": q.get("asof")}
        tec = MD.technical_summary(fetch_history(ticker)["rows"], q.get("price"), q.get("day_change_pct"))
        for k in ("sma50", "sma200", "rsi14", "tendencia", "distancia_a_maximo_pct"):
            item[k] = tec.get(k)
        return item
    except Exception as e:  # un instrumento caído no tumba el pulso
        return {"ticker": ticker, "nombre": nombre, "error": str(e) or e.__class__.__name__}


def _semaforo(spy, vix_price):
    if spy is None or spy.get("price") is None:
        return "sin_datos"
    price, s50, s200 = spy["price"], spy.get("sma50"), spy.get("sma200")
    if (vix_price is not None and vix_price >= 25) or (s200 and price < s200):
        return "miedo"
    if (vix_price is not None and vix_price >= 20) or (s50 and price < s50):
        return "cauteloso"
    return "normal"


def _tipo_dia(chg):
    if chg is None:
        return None
    return "rojo" if chg <= -1 else ("verde" if chg >= 1 else "tranquilo")


def _lectura(spy, qqq, vix_price, semaforo, tipo_dia):
    if spy is None:
        return "Sin datos de mercado ahora: no se pudo leer el S&P 500."
    if vix_price is None:
        vix_txt = "VIX sin dato."
    else:
        estado = "miedo alto" if vix_price >= 25 else ("nerviosismo" if vix_price >= 20 else "calma")
        vix_txt = f"VIX en {vix_price:.1f}: {estado}."
    base = (f"S&P 500 {_pct(spy.get('day_change_pct'))} y Nasdaq 100 "
            f"{_pct((qqq or {}).get('day_change_pct'))} hoy. {vix_txt}")
    if tipo_dia == "rojo":
        frase = LECTURA_DIA["rojo_miedo" if semaforo == "miedo" else "rojo"]
    elif tipo_dia == "verde":
        frase = LECTURA_DIA["verde"]
    elif tipo_dia == "tranquilo":
        frase = LECTURA_DIA["tranquilo"]
    else:
        frase = "Sin variación diaria del S&P 500 disponible."
    return base + " " + frase


def pulse(fetch_quote=None, fetch_history=None, now=None) -> dict:
    """Lee los instrumentos de referencia y resume el día con reglas explícitas."""
    fetch_quote = fetch_quote or MD.fetch_quote
    fetch_history = fetch_history or MD.fetch_history
    items = [_instrument(tk, nombre, fetch_quote, fetch_history) for tk, nombre in INSTRUMENTS]
    ok = {i["ticker"]: i for i in items if "error" not in i and i.get("price") is not None}
    spy, qqq, vix = ok.get("SPY"), ok.get("QQQ"), ok.get("^VIX")
    vix_price = vix["price"] if vix else None
    semaforo = _semaforo(spy, vix_price)
    tipo_dia = _tipo_dia(spy.get("day_change_pct")) if spy else None
    return {
        "semaforo": semaforo, "tipo_dia": tipo_dia,
        "lectura": _lectura(spy, qqq, vix_price, semaforo, tipo_dia),
        "instrumentos": items,
        "fetched_at": _now(now).isoformat(timespec="seconds"),
        "fuente": FUENTE, "nota": NOTA,
    }


def cached_pulse(max_age_s=PULSE_MAX_AGE_S, now=None, **kw) -> dict:
    t = _now(now)
    cached, at = _pulse_cache["value"], _pulse_cache["at"]
    if cached is not None and at is not None:
        limit = max_age_s if cached["semaforo"] != "sin_datos" else min(max_age_s, PULSE_ERROR_MAX_AGE_S)
        if (t - at).total_seconds() < limit:
            return cached
    value = pulse(now=t, **kw)
    _pulse_cache.update(at=t, value=value)
    return value


def resumen_pulse(p) -> dict | None:
    """Versión compacta para trade_check y el contexto de Luna."""
    if not p:
        return None
    return {k: p.get(k) for k in ("semaforo", "tipo_dia", "lectura")}


# ---------- niveles por acción ----------

def levels(ticker, fetch_quote=None, fetch_history=None, now=None) -> dict:
    """Cotización viva + technical_summary con niveles ATR. Lanza MarketDataError
    si no hay precio; el histórico fallido queda como `tecnica.error`."""
    fetch_quote = fetch_quote or MD.fetch_quote
    fetch_history = fetch_history or MD.fetch_history
    q = fetch_quote(ticker)
    if q.get("price") is None:
        raise MD.MarketDataError(f"Sin precio para {ticker}")
    try:
        hist = fetch_history(ticker)
        tec = MD.technical_summary(hist["rows"], q["price"], q.get("day_change_pct"))
        tec["fuente"], tec["obtenido"] = hist["source"], hist["fetched_at"]
    except MD.MarketDataError as e:
        tec = {"error": str(e)}
    return {
        "ticker": ticker, "quote": q,
        "precio": {"valor": q["price"], "asof": q.get("asof"), "fuente": q.get("source"),
                   "day_change_pct": q.get("day_change_pct")},
        "tecnica": tec, "niveles": tec.get("niveles"),
        "fetched_at": _now(now).isoformat(timespec="seconds"),
    }


def cached_levels(ticker, max_age_s=LEVELS_MAX_AGE_S, now=None, **kw):
    """Devuelve (niveles, fresco): `fresco` indica que se descargó ahora."""
    t = _now(now)
    hit = _levels_cache.get(ticker)
    if hit and (t - hit[0]).total_seconds() < max_age_s:
        return hit[1], False
    value = levels(ticker, now=t, **kw)
    _levels_cache[ticker] = (t, value)
    return value, True


def levels_if_cached(ticker, max_age_s=LEVELS_MAX_AGE_S, now=None):
    hit = _levels_cache.get(ticker)
    if hit and (_now(now) - hit[0]).total_seconds() < max_age_s:
        return hit[1]
    return None


def posicion_vs_niveles(price, niveles, avg_cost, qty) -> dict | None:
    """Distancias desde el costo promedio del usuario (None si no hay costo)."""
    if not avg_cost or avg_cost <= 0:
        return None
    out = {"avg_cost": avg_cost, "qty": qty,
           "desde_costo_pct": round((price / avg_cost - 1) * 100, 1) if price else None,
           "stop_desde_costo_pct": None, "toma_desde_costo_pct": None}
    if niveles:
        out["stop_desde_costo_pct"] = round((niveles["stop_loss"] / avg_cost - 1) * 100, 1)
        out["toma_desde_costo_pct"] = round((niveles["toma_parcial"] / avg_cost - 1) * 100, 1)
    return out
