"""Módulos 4 y 5: análisis fundamental y valoración con supuestos explícitos.

Todo cálculo distingue: HECHO (dato con fuente), CÁLCULO (derivado), ESTIMACIÓN
(depende de supuestos modificables) y lo que FALTA. Nunca se rellenan huecos
con cifras inventadas: si falta un dato, la métrica se reporta como faltante.
"""

FUND_FIELDS = [
    ("revenue", "Ingresos anuales (USD)"), ("revenue_growth_pct", "Crecimiento de ingresos %"),
    ("eps", "Beneficio por acción (EPS)"), ("eps_fwd", "EPS estimado próximo año"),
    ("eps_growth_pct", "Crecimiento del EPS %"), ("fcf", "Flujo de caja libre (USD)"),
    ("shares_out", "Acciones en circulación"), ("debt", "Deuda total (USD)"),
    ("cash", "Efectivo e inversiones (USD)"), ("gross_margin_pct", "Margen bruto %"),
    ("op_margin_pct", "Margen operativo %"), ("roic_pct", "Retorno sobre el capital %"),
    ("ebitda", "EBITDA (USD)"), ("dividend_yield_pct", "Rentabilidad por dividendo %"),
    ("buybacks", "Recompras (USD/año)"), ("next_earnings_date", "Próximos resultados (fecha)"),
    ("moat", "Ventaja competitiva (texto)"), ("key_risks", "Riesgos principales (texto)"),
    ("business_model", "Modelo de negocio (texto)"), ("customer_concentration", "Dependencia de clientes (texto)"),
]

# Campos de FUND_FIELDS que no son cifras: la SEC no los provee y los informes
# los registran como texto o fecha; se usan para el resumen de faltantes.
TEXT_FUND_FIELDS = {"moat", "key_risks", "business_model", "customer_concentration",
                    "next_earnings_date"}


def _num(d, key):
    v = d.get(key)
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fundamental_scores(f: dict) -> dict:
    """Puntuaciones 0–10 por dimensión, cada una con motivo y datos faltantes."""
    missing, out = [], {}

    def score(name, value, reason):
        out[name] = {"score": value, "reason": reason}

    gm, om, roic = _num(f, "gross_margin_pct"), _num(f, "op_margin_pct"), _num(f, "roic_pct")
    if om is None and gm is None and roic is None:
        score("calidad", None, "Faltan márgenes y ROIC")
        missing.append("márgenes / ROIC")
    else:
        pts = 0.0; n = 0
        if gm is not None: pts += min(gm / 60, 1) * 10; n += 1
        if om is not None: pts += min(om / 35, 1) * 10; n += 1
        if roic is not None: pts += min(roic / 25, 1) * 10; n += 1
        score("calidad", round(pts / n, 1), f"Margen bruto {gm}%, operativo {om}%, ROIC {roic}%")

    debt, cash, fcf = _num(f, "debt"), _num(f, "cash"), _num(f, "fcf")
    if debt is None or cash is None:
        score("solidez_financiera", None, "Faltan deuda y/o efectivo")
        missing.append("deuda / efectivo")
    else:
        net = cash - debt
        base = 7 if net >= 0 else max(0, 5 - min(debt / max(cash, 1), 5))
        if fcf is not None and fcf > 0:
            base = min(10, base + 2)
        score("solidez_financiera", round(base, 1),
              f"Efectivo neto {'positivo' if net >= 0 else 'negativo'} ({net:,.0f}); FCF {'positivo' if (fcf or 0) > 0 else 'desconocido o negativo'}")

    rg, eg = _num(f, "revenue_growth_pct"), _num(f, "eps_growth_pct")
    if rg is None and eg is None:
        score("crecimiento", None, "Faltan tasas de crecimiento")
        missing.append("crecimiento de ingresos/EPS")
    else:
        g = max(x for x in (rg, eg) if x is not None)
        score("crecimiento", round(max(0, min(g / 40, 1)) * 10, 1), f"Ingresos {rg}% · EPS {eg}%")

    if f.get("moat"):
        score("previsibilidad", 6.0, f"Ventaja declarada: {f['moat'][:80]} (evaluación cualitativa)")
    else:
        score("previsibilidad", None, "Describe la ventaja competitiva para evaluarla")
        missing.append("ventaja competitiva")

    if f.get("key_risks"):
        score("riesgo", 5.0, f"Riesgos declarados: {f['key_risks'][:100]} (revisar en cada tesis)")
    else:
        score("riesgo", None, "Registra los riesgos principales (regulatorios, tecnológicos, clientes)")
        missing.append("riesgos declarados")

    return {"scores": out, "missing": missing,
            "nota": "Una empresa excelente no es automáticamente una buena compra a cualquier precio: ver Valoración."}


def multiples(price: float, f: dict) -> dict:
    """Múltiplos calculados solo con datos disponibles; el resto se marca faltante."""
    out, missing = {}, []
    eps, eps_fwd = _num(f, "eps"), _num(f, "eps_fwd")
    growth = _num(f, "eps_growth_pct") or _num(f, "revenue_growth_pct")
    shares, revenue, fcf = _num(f, "shares_out"), _num(f, "revenue"), _num(f, "fcf")
    debt, cash, ebitda = _num(f, "debt"), _num(f, "cash"), _num(f, "ebitda")

    if eps and eps > 0:
        out["pe"] = round(price / eps, 1)
    else:
        missing.append("P/E (falta EPS positivo)")
    if eps_fwd and eps_fwd > 0:
        out["pe_forward"] = round(price / eps_fwd, 1)
    else:
        missing.append("P/E futuro (falta EPS estimado)")
    if eps and eps > 0 and growth and growth > 0:
        out["peg"] = round((price / eps) / growth, 2)
    if shares and revenue:
        out["price_to_sales"] = round(price * shares / revenue, 1)
    else:
        missing.append("P/S (faltan acciones o ingresos)")
    if shares and fcf and fcf > 0:
        out["price_to_fcf"] = round(price * shares / fcf, 1)
    else:
        missing.append("P/FCF (falta FCF)")
    if shares and ebitda and ebitda > 0 and debt is not None and cash is not None:
        out["ev_ebitda"] = round((price * shares + debt - cash) / ebitda, 1)
    else:
        missing.append("EV/EBITDA (faltan EBITDA/deuda/efectivo)")
    return {"multiples": out, "missing": missing}


DEFAULT_DCF = {"years": 10, "growth_1_5_pct": 15.0, "growth_6_10_pct": 8.0,
               "terminal_growth_pct": 2.5, "discount_rate_pct": 10.0}


def dcf_per_share(fcf: float, shares: float, a: dict) -> float | None:
    """Flujo de caja descontado clásico por acción. Devuelve None si no es calculable."""
    if not fcf or not shares or fcf <= 0:
        return None
    r = a["discount_rate_pct"] / 100
    tg = a["terminal_growth_pct"] / 100
    if r <= tg:
        return None
    flow, total = fcf, 0.0
    for year in range(1, int(a["years"]) + 1):
        g = a["growth_1_5_pct"] / 100 if year <= 5 else a["growth_6_10_pct"] / 100
        flow *= (1 + g)
        total += flow / (1 + r) ** year
    terminal = flow * (1 + tg) / (r - tg) / (1 + r) ** int(a["years"])
    return (total + terminal) / shares


def valuation_scenarios(price: float, f: dict, assumptions: dict | None = None) -> dict:
    """Tres escenarios (pesimista/base/optimista) con supuestos visibles y modificables.

    Devuelve rangos, nunca un único precio objetivo exacto.
    """
    base = {**DEFAULT_DCF, **(assumptions or {})}
    fcf, shares = _num(f, "fcf"), _num(f, "shares_out")
    variants = {
        "pesimista": {**base, "growth_1_5_pct": base["growth_1_5_pct"] * 0.5,
                      "growth_6_10_pct": base["growth_6_10_pct"] * 0.5,
                      "discount_rate_pct": base["discount_rate_pct"] + 1.5},
        "base": base,
        "optimista": {**base, "growth_1_5_pct": base["growth_1_5_pct"] * 1.25,
                      "discount_rate_pct": max(base["discount_rate_pct"] - 0.5, base["terminal_growth_pct"] + 1)},
    }
    out = {}
    for name, a in variants.items():
        v = dcf_per_share(fcf, shares, a)
        out[name] = {
            "valor_estimado_por_accion": round(v, 2) if v else None,
            "margen_de_seguridad_pct": round((v / price - 1) * 100, 1) if v and price else None,
            "supuestos": {k: round(val, 2) if isinstance(val, float) else val for k, val in a.items()},
        }
    calculable = all(x["valor_estimado_por_accion"] for x in out.values())
    return {"escenarios": out, "calculable": calculable,
            "faltantes": [] if calculable else ["FCF y acciones en circulación (con fuente) para calcular el DCF"],
            "nota": "ESTIMACIÓN dependiente de supuestos modificables; no es una predicción ni una certeza."}
