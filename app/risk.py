"""Módulo 8: gestión de riesgo de la cartera (pesos, concentración, límites)."""

DEFAULT_LIMITS = {
    "max_position_pct": 25.0, "max_sector_pct": 40.0, "max_trade_pct": 10.0,
    "max_tolerable_loss_pct": 30.0, "min_cash_reserve": 0.0, "max_trades_per_month": 8,
}

# Sectores conocidos para los tickers frecuentes; el usuario puede corregirlos.
KNOWN_SECTORS = {"NVDA": "Tecnología (semiconductores/IA)", "MSFT": "Tecnología (software/nube/IA)",
                 "AAPL": "Tecnología", "GOOGL": "Tecnología", "GOOG": "Tecnología",
                 "AMZN": "Consumo/Tecnología", "META": "Tecnología", "TSLA": "Automotriz/Tecnología"}

CORRELATED_GROUPS = [
    ({"NVDA", "MSFT", "AAPL", "GOOGL", "GOOG", "AMZN", "META", "AMD", "TSM", "AVGO"},
     "tecnología / tendencia de inteligencia artificial"),
]


def portfolio_risk(positions: list, cash: float, limits: dict) -> dict:
    """positions: [{ticker, sector, market_value, invested, ...}]. Todo peso es CÁLCULO."""
    lm = {**DEFAULT_LIMITS, **(limits or {})}
    cash = cash or 0  # normaliza None una sola vez: abajo se compara y formatea sin volver a comprobar
    total_pos = sum(p.get("market_value") or 0 for p in positions)
    total = total_pos + cash
    if total <= 0:
        return {"error": "Sin valores de mercado disponibles para calcular riesgo"}

    weights = []
    breaches = []
    for p in positions:
        w = (p.get("market_value") or 0) / total * 100
        weights.append({"ticker": p["ticker"], "peso_pct": round(w, 2),
                        "sector": p.get("sector") or KNOWN_SECTORS.get(p["ticker"], "sin clasificar")})
        if w > lm["max_position_pct"]:
            breaches.append({"tipo": "posicion", "ticker": p["ticker"],
                             "detalle": f"{p['ticker']} pesa {w:.1f}% y tu máximo por empresa es {lm['max_position_pct']}%"})

    sectors = {}
    for w in weights:
        sectors[w["sector"]] = sectors.get(w["sector"], 0) + w["peso_pct"]
    for s, w in sectors.items():
        if w > lm["max_sector_pct"]:
            breaches.append({"tipo": "sector", "ticker": s,
                             "detalle": f"El sector «{s}» pesa {w:.1f}% y tu máximo por sector es {lm['max_sector_pct']}%"})

    # Índice Herfindahl (0–10000): >2500 se considera concentrado
    hhi = round(sum(w["peso_pct"] ** 2 for w in weights))
    # Diversificación efectiva: número equivalente de posiciones independientes
    eff_n = round(10000 / hhi, 1) if hhi else None

    corr_notes = []
    tickers = {p["ticker"] for p in positions}
    for group, label in CORRELATED_GROUPS:
        hit = tickers & group
        if len(hit) >= 2:
            gw = sum(w["peso_pct"] for w in weights if w["ticker"] in hit)
            corr_notes.append(f"{', '.join(sorted(hit))} comparten exposición a {label} "
                              f"({gw:.1f}% de la cartera): tener ambas NO es diversificación suficiente.")

    cash_pct = round((cash or 0) / total * 100, 2)
    if cash < lm["min_cash_reserve"]:
        breaches.append({"tipo": "efectivo", "ticker": "CASH",
                         "detalle": f"Efectivo ({cash:.2f}) por debajo de tu reserva mínima ({lm['min_cash_reserve']:.2f})"})

    return {
        "valor_total": round(total, 2), "efectivo": round(cash or 0, 2), "efectivo_pct": cash_pct,
        "pesos": weights, "sectores": [{"sector": s, "peso_pct": round(w, 2)} for s, w in sectors.items()],
        "hhi": hhi, "diversificacion_efectiva": eff_n,
        "nivel_concentracion": "alta" if hhi > 2500 else ("media" if hhi > 1500 else "baja"),
        "correlacion": corr_notes, "incumplimientos": breaches, "limites": lm,
    }


def stress_position(market_value: float, drops=(10, 20, 30, 50)) -> list:
    return [{"caida_pct": d, "perdida_usd": round(market_value * d / 100, 2),
             "valor_restante": round(market_value * (1 - d / 100), 2)} for d in drops]
