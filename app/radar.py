"""Radar de oportunidades: universo fijo de emisoras de EE.UU. con 10-K más
la watchlist y la cartera del usuario, puntuado con precio real (Yahoo) y
fundamentales del último 10-K (SEC).

`screen` es pura: recibe el precio y los fundamentales ya guardados, nunca
toca la red ni la base de datos. El veredicto es apoyo a la decisión del
usuario, no una recomendación ni una orden.
"""
from . import analysis as AN

# Emisoras estadounidenses grandes y líquidas que presentan 10-K ante la SEC.
# No se incluyen ETF ni emisoras extranjeras que reportan 20-F (p. ej. TSM):
# secdata.py no extrae fundamentales de esas presentaciones.
UNIVERSE = {
    # Tecnología
    "AAPL": "Tecnología", "MSFT": "Tecnología", "NVDA": "Tecnología",
    "GOOGL": "Tecnología", "AMZN": "Consumo/Tecnología", "META": "Tecnología",
    "AVGO": "Tecnología", "AMD": "Tecnología", "ORCL": "Tecnología",
    "CRM": "Tecnología", "ADBE": "Tecnología", "QCOM": "Tecnología",
    "INTC": "Tecnología", "MU": "Tecnología", "CSCO": "Tecnología",
    "IBM": "Tecnología", "TXN": "Tecnología",
    # Comunicaciones y entretenimiento
    "NFLX": "Comunicaciones/entretenimiento", "DIS": "Comunicaciones/entretenimiento",
    "CMCSA": "Comunicaciones/entretenimiento",
    "T": "Comunicaciones", "VZ": "Comunicaciones", "TMUS": "Comunicaciones",
    # Financiero
    "JPM": "Financiero", "V": "Financiero", "MA": "Financiero",
    "BAC": "Financiero", "GS": "Financiero", "MS": "Financiero",
    "AXP": "Financiero", "BLK": "Financiero", "WFC": "Financiero",
    "SCHW": "Financiero", "PYPL": "Financiero",
    # Salud
    "JNJ": "Salud", "UNH": "Salud", "LLY": "Salud", "ABBV": "Salud",
    "MRK": "Salud", "TMO": "Salud", "ABT": "Salud", "ISRG": "Salud",
    "PFE": "Salud", "AMGN": "Salud", "CVS": "Salud",
    # Consumo
    "WMT": "Consumo", "COST": "Consumo", "HD": "Consumo", "MCD": "Consumo",
    "NKE": "Consumo", "SBUX": "Consumo", "PG": "Consumo", "KO": "Consumo",
    "PEP": "Consumo", "MDLZ": "Consumo", "CL": "Consumo", "LOW": "Consumo",
    "TGT": "Consumo", "TSLA": "Automotriz/Tecnología",
    # Industrial
    "BA": "Industrial", "CAT": "Industrial", "GE": "Industrial",
    "HON": "Industrial", "UPS": "Industrial", "DE": "Industrial",
    "LMT": "Industrial", "UNP": "Industrial", "RTX": "Industrial",
    "FDX": "Industrial",
    # Energía
    "XOM": "Energía", "CVX": "Energía", "COP": "Energía", "SLB": "Energía",
    "EOG": "Energía",
    # Materiales y servicios públicos
    "LIN": "Materiales", "SHW": "Materiales", "APD": "Materiales",
    "NEE": "Servicios públicos",
}

VERDICT_LABELS = {"barata_y_buena": "Barata y buena", "precio_justo": "Precio justo",
                  "buena_pero_cara": "Buena pero cara", "cuidado": "Cuidado",
                  "faltan_datos": "Faltan datos"}
VERDICT_ORDER = ["barata_y_buena", "precio_justo", "buena_pero_cara",
                 "cuidado", "faltan_datos"]


def _num(d, key):
    v = d.get(key)
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def screen(ticker, sector, price, fund) -> dict:
    """Puntúa un activo con lo ya guardado: calidad media de los scores
    fundamentales y margen de seguridad del DCF base con crecimiento
    conservador (el real del 10-K acotado a 0–15 %)."""
    fund = fund or {}
    scores = AN.fundamental_scores(fund) if fund else {"scores": {}}
    vals = [v["score"] for v in scores["scores"].values() if v["score"] is not None]
    calidad = round(sum(vals) / len(vals), 1) if vals else None

    growth = _num(fund, "revenue_growth_pct")
    eps = _num(fund, "eps")
    fcf = _num(fund, "fcf")
    shares = _num(fund, "shares_out")

    mos = None
    if price and price > 0 and growth is not None:
        g_supuesto = min(max(growth, 0), 15)
        scen = AN.valuation_scenarios(price, fund, {"growth_1_5_pct": g_supuesto})
        if scen["calculable"]:
            mos = scen["escenarios"]["base"]["margen_de_seguridad_pct"]

    pe = round(price / eps, 1) if price and eps and eps > 0 else None
    pfcf = round(price / (fcf / shares), 1) \
        if price and fcf and shares and fcf > 0 and shares > 0 else None
    crec = growth

    if calidad is None or mos is None:
        veredicto = "faltan_datos"
    elif calidad < 6:
        veredicto = "cuidado"
    elif mos >= 15:
        veredicto = "barata_y_buena"
    elif mos >= -15:
        veredicto = "precio_justo"
    else:
        veredicto = "buena_pero_cara"

    motivos = []
    if calidad is not None:
        motivos.append(f"Calidad {calidad}/10")
    if mos is not None:
        motivos.append(f"Margen de seguridad {mos}%")
    if pe is not None:
        motivos.append(f"P/E {pe}")
    if crec is not None:
        motivos.append(f"Crec. ingresos {crec}%")
    motivos = motivos[:3]
    if calidad is not None and calidad < 6:
        peor = min((v for v in scores["scores"].values() if v["score"] is not None),
                   key=lambda v: v["score"], default=None)
        if peor:
            motivos.append(peor["reason"])
    return {"ticker": ticker, "sector": sector, "calidad": calidad, "mos": mos,
            "pe": pe, "pfcf": pfcf, "crec": crec, "veredicto": veredicto,
            "motivos": motivos}
