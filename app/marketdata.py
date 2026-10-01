"""Módulo 3: datos de mercado con fuente, fecha/hora y estado de actualización.

Fuente primaria: API pública de gráficos de Yahoo Finance (sin clave). Si no
está disponible, el sistema lo informa y permite ingreso manual. Ningún dato
se presenta sin su fuente y antigüedad; `staleness()` clasifica la frescura.
"""
import json
import urllib.request
from datetime import datetime, timezone

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={rng}&interval=1d"
HEADERS = {"User-Agent": "Mozilla/5.0 (InversorHapi-MVP)"}
TIMEOUT = 10


class MarketDataError(Exception):
    pass


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise MarketDataError(f"Fuente de datos no disponible ({e.__class__.__name__}). "
                              "Puedes ingresar el precio manualmente.") from e


def fetch_quote(ticker: str) -> dict:
    data = _fetch_json(YAHOO_CHART.format(ticker=ticker.upper(), rng="5d"))
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise MarketDataError(f"Sin datos para {ticker}")
    meta = result["meta"]
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    ts = meta.get("regularMarketTime")
    asof = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds") if ts else None
    return {
        "ticker": ticker.upper(), "price": price, "currency": meta.get("currency", "USD"),
        "asof": asof, "source": "Yahoo Finance (chart API)",
        "day_change_pct": round((price / prev - 1) * 100, 2) if price and prev else None,
    }


def fetch_history(ticker: str, rng: str = "1y") -> dict:
    data = _fetch_json(YAHOO_CHART.format(ticker=ticker.upper(), rng=rng))
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result or not result.get("timestamp"):
        raise MarketDataError(f"Sin histórico para {ticker}")
    quote = result["indicators"]["quote"][0]
    stamps = result["timestamp"]
    closes = quote.get("close") or []

    def _col(name):  # Yahoo puede omitir una serie; no inventamos valores
        col = quote.get(name) or []
        return col if len(col) == len(stamps) else [None] * len(stamps)

    highs, lows, volumes = _col("high"), _col("low"), _col("volume")
    # adjclose (retorno total, con dividendos) vive en otra serie de indicators;
    # si falta o no se alinea con los timestamps, queda None en vez de inventarse.
    adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose") or []
    adjclose = adj if len(adj) == len(stamps) else [None] * len(stamps)
    rows = [
        {"date": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
         "close": c, "volume": volumes[i], "high": highs[i], "low": lows[i],
         "adjclose": adjclose[i]}
        for i, (t, c) in enumerate(zip(stamps, closes)) if c is not None
    ]
    return {"ticker": ticker.upper(), "source": "Yahoo Finance (chart API)",
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows}


def staleness(asof_iso: str | None) -> dict:
    """Clasifica la antigüedad de un dato para no usar datos viejos como actuales."""
    if not asof_iso:
        return {"age_hours": None, "status": "sin_fecha", "usable_as_current": False}
    try:
        asof = datetime.fromisoformat(asof_iso.replace("Z", "+00:00"))
        if asof.tzinfo is None:
            asof = asof.replace(tzinfo=timezone.utc)
    except ValueError:
        return {"age_hours": None, "status": "sin_fecha", "usable_as_current": False}
    hours = (datetime.now(timezone.utc) - asof).total_seconds() / 3600
    if hours < -5 / 60:
        return {"age_hours": round(hours, 1), "status": "fecha_futura", "usable_as_current": False}
    hours = max(0, hours)  # tolerancia a desfases de reloj de hasta cinco minutos
    if hours <= 24:
        status = "actual"
    elif hours <= 24 * 5:
        status = "reciente"  # cubre fines de semana / feriados de mercado
    else:
        status = "desactualizado"
    return {"age_hours": round(hours, 1), "status": status, "usable_as_current": hours <= 24 * 5}


# ---------- indicadores técnicos (Módulo 6, información complementaria) ----------

def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g, avg_l = sum(gains) / period, sum(losses) / period
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 1)


def atr14(rows: list, period: int = 14):
    """Rango verdadero medio (ATR) simple de los últimos `period` días.

    TR_i = max(high−low, |high−close_prev|, |low−close_prev|); si una fila no trae
    high/low se usa |close_i − close_prev|. None si no hay `period`+1 filas."""
    if len(rows) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        row, prev = rows[i], rows[i - 1]["close"]
        hi, lo = row.get("high"), row.get("low")
        if hi is None or lo is None:
            trs.append(abs(row["close"] - prev))
        else:
            trs.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
    return round(sum(trs) / period, 4)


LECTURA_SEMAFORO = {
    "descuento": "Descuento en tendencia sana: día razonable para comprar escalonado.",
    "estirada": "Estirada: si ya la tienes, es razonable vender una parte; si no, espera.",
    "bajista": "Tendencia bajista: no promediar a la baja sin una tesis clara.",
    "neutral": "Sin señal técnica fuerte: decide por valoración y tesis.",
}
REGLA_NIVELES = "Niveles por volatilidad (ATR14 ×2 stop, ×3 toma parcial). Regla técnica, no predicción."


def _niveles(p, atr, rsi14, s20, s50, s200, soporte, day_change_pct):
    """Niveles operativos por volatilidad. Regla técnica explícita, no predicción."""
    if atr is None or not p or p <= 0:
        return None
    stop, toma = round(p - 2 * atr, 2), round(p + 3 * atr, 2)
    estirada = rsi14 is not None and rsi14 >= 70
    if estirada:
        zona = None
        nota = (f"Estirada: espera un retroceso hacia la media de 20 días (${round(s20, 2)})"
                if s20 else "Estirada: espera un retroceso antes de entrar")
    else:
        # El soporte puede quedar por encima del precio vivo si este cayó bajo el mínimo
        # de 60 días; en ese caso la zona parte de p − ATR para no invertir el rango.
        lower = max(soporte, p - atr) if soporte is not None and soporte <= p else p - atr
        zona = [round(lower, 2), round(p, 2)]
        nota = "Compra escalonada dentro de la zona, nunca todo de golpe"
    if rsi14 is not None and rsi14 < 35 and (s200 is None or p > s200):
        semaforo = "descuento"
    elif estirada:
        semaforo = "estirada"
    elif s200 and p < s200 and s50 and s50 < s200:
        semaforo = "bajista"
    else:
        semaforo = "neutral"
    if day_change_pct is None:
        tipo_dia = None
    else:
        tipo_dia = "rojo" if day_change_pct <= -2 else ("verde" if day_change_pct >= 2 else "normal")
    return {
        "precio_base": round(p, 2), "atr14": atr,
        "stop_loss": stop, "stop_loss_pct": round((stop / p - 1) * 100, 1),
        "toma_parcial": toma, "toma_parcial_pct": round((toma / p - 1) * 100, 1),
        "entrada_zona": zona, "entrada_nota": nota,
        "semaforo": semaforo, "lectura": LECTURA_SEMAFORO[semaforo],
        "tipo_dia": tipo_dia, "regla": REGLA_NIVELES,
    }


def technical_summary(history_rows: list, price=None, day_change_pct=None) -> dict:
    """Indicadores sobre el histórico. `price` (cotización viva) manda en niveles y
    distancia al máximo; si falta, se usa el último cierre."""
    closes = [r["close"] for r in history_rows]
    if len(closes) < 30:
        return {"error": "Histórico insuficiente para análisis técnico"}
    last = closes[-1]
    p = price if price is not None and price > 0 else last
    s20, s50, s200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    hi, lo = max(closes), min(closes)
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    vol_daily = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
    # Caída máxima del periodo (drawdown)
    peak, max_dd = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        max_dd = min(max_dd, c / peak - 1)
    trend = "alcista" if s50 and s200 and s50 > s200 and p > s50 else (
        "bajista" if s50 and p < s50 else "lateral/indefinida")
    soporte = round(min(closes[-60:]), 2) if len(closes) >= 60 else round(lo, 2)
    rsi14, atr = rsi(closes), atr14(history_rows)
    return {
        "precio": round(p, 2), "ultimo_cierre": round(last, 2),
        "sma20": round(s20, 2) if s20 else None, "sma50": round(s50, 2) if s50 else None,
        "sma200": round(s200, 2) if s200 else None, "rsi14": rsi14, "atr14": atr,
        "tendencia": trend,
        "maximo_periodo": round(hi, 2), "minimo_periodo": round(lo, 2),
        "distancia_a_maximo_pct": round((p / max(hi, p) - 1) * 100, 1),
        "volatilidad_anualizada_pct": round(vol_daily * (252 ** 0.5) * 100, 1),
        "caida_maxima_periodo_pct": round(max_dd * 100, 1),
        "soporte_aproximado": soporte,
        "resistencia_aproximada": round(max(closes[-60:]), 2) if len(closes) >= 60 else round(hi, 2),
        "niveles": _niveles(p, atr, rsi14, s20, s50, s200, soporte, day_change_pct),
        "nota": "Indicadores complementarios; nunca son razón única para operar.",
    }
