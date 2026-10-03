"""Módulos 4-15: análisis y decisión, riesgo, oportunidades, alertas,
diario de inversión y panel. El motor de decisión es determinista; la IA solo
explica o cuestiona, nunca propone por su cuenta."""
import json
import math
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import ai_review as RV
from .. import analysis as AN
from .. import brecha as BR
from .. import cuerdas as CU
from .. import db as D
from .. import decisions as DE
from .. import marketdata as MD
from .. import marketpulse as MP
from .. import risk as RK
from .. import scoreboard as SB
from .. import secdata as SEC
from .. import tradesync as TS
from ..deps import DISCLAIMER, conn_dep, current_user
from . import marcador as MARC
from .marcador import bloquear_en_modo_plan
from .market import _sec_fundamentals, store_quote
from .portfolio import cash_unsupported, enrich_positions, portfolio, without_current_value

router = APIRouter()


class JournalIn(BaseModel):
    ticker: str = ""
    action: str = "revision"
    tesis: str = ""
    riesgos: str = ""
    condicion_invalidacion: str = ""
    precio: Optional[float] = None
    review_date: str = ""


class TradeCheckIn(BaseModel):
    ticker: str
    side: Literal["comprar", "vender"]
    amount_usd: float
    assumptions: Optional[dict] = None


class CandidateIn(BaseModel):
    ticker: str
    name: str = ""
    source: str
    data: dict  # calidad, crecimiento, valoracion, margen_seguridad, solidez, riesgo (0-10), tesis, catalizadores, condicion_entrada, condicion_espera, condicion_invalidacion


# ---------- Módulos 4-7 y 14: análisis y recomendación ----------

@router.post("/api/analysis/{ticker}")
def analyze(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Modo plan: con el ETF bajo la meta, el análisis completo de una acción
    individual también es sirena (409). El ETF del plan sí se analiza."""
    tk = ticker.upper()
    mp = MARC.modo_plan_estado(conn, uid)
    if mp["activo"] and tk not in SB.ETF_META:
        etf_plan = D.get_setting(conn, uid, "etf_plan", SB.SETTINGS_DEFAULTS["etf_plan"])
        raise HTTPException(409, MARC.modo_plan_detalle(mp, etf_plan))
    return _analysis_report(tk, body, uid, conn, completo=True)


def _analysis_report(tk, body, uid, conn, *, completo=True):
    """Cuerpo del análisis: con completo=False no se descarga el histórico
    (technical=None); lo usa trade_check en modo plan."""
    positions = enrich_positions(conn, uid)
    pos = next((p for p in positions if p["ticker"] == tk), None)
    frow = conn.execute("SELECT * FROM fundamentals WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
    fund = json.loads(frow["data"]) if frow else {}
    price_row = D.latest_price(conn, tk)
    price_st = MD.staleness(price_row["asof"]) if price_row else {"status": "sin_precio", "usable_as_current": False}
    if (not price_row or not price_st["usable_as_current"] or
            price_row["price"] is None or not math.isfinite(price_row["price"]) or price_row["price"] <= 0 or
            (price_row["currency"] or "USD").upper() != "USD"):
        estado = price_st["status"]
        raise HTTPException(400, f"Precio de mercado no utilizable en USD ({estado}). Actualiza precios o "
                                 "ingresa uno manual en USD con fuente y fecha; una captura no sustituye la cotización.")
    price = price_row["price"]
    price_st = price_st["status"]
    missing_value = without_current_value(positions)
    if missing_value:
        raise HTTPException(400, "Cartera sin valoración comparable en USD para: " + ", ".join(missing_value)
                            + ". Actualiza sus precios antes de calcular pesos o proponer decisiones.")
    cash_check = conn.execute("SELECT currency FROM cash WHERE user_id=?", (uid,)).fetchone()
    if cash_unsupported(cash_check):
        raise HTTPException(400, "El efectivo no está en USD; falta un tipo de cambio verificable")

    fscores = AN.fundamental_scores(fund) if fund else {"scores": {}, "missing": ["todos los fundamentales"],
                                                        "nota": "Registra fundamentales con fuente y fecha para el análisis"}
    mult = AN.multiples(price, fund) if fund else {"multiples": {}, "missing": ["fundamentales no registrados"]}
    scen = AN.valuation_scenarios(price, fund, body.get("assumptions"))

    technical = None
    if completo:
        try:
            hist = MD.fetch_history(tk)
            technical = MD.technical_summary(hist["rows"], price, price_row.get("day_change_pct"))
            technical["fuente"] = hist["source"]
            technical["obtenido"] = hist["fetched_at"]
        except MD.MarketDataError as e:
            technical = {"error": str(e)}

    prof = CU.perfil_efectivo(conn, uid)
    limits = CU.limites_efectivos(conn, uid)
    cash_row = conn.execute("SELECT amount FROM cash WHERE user_id=?", (uid,)).fetchone()
    total = sum(p["market_value"] or 0 for p in positions) + (cash_row["amount"] if cash_row else 0)
    weight = round((pos["market_value"] or 0) / total * 100, 2) if pos and total else None
    thesis = conn.execute("SELECT id FROM journal WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
    mos = scen["escenarios"]["base"]["margen_de_seguridad_pct"] if scen["calculable"] else None

    ctx = {
        "ticker": tk, "price": price, "price_status": price_st,
        "qty": pos["qty"] if pos else 0, "market_value": pos["market_value"] if pos else 0,
        "invested": pos["invested"] if pos else None, "avg_cost": pos["avg_cost"] if pos else None,
        "unrealized_pl": pos["unrealized_pl"] if pos else 0, "weight_pct": weight,
        "max_position_pct": (limits or {}).get("max_position_pct", RK.DEFAULT_LIMITS["max_position_pct"]),
        "margin_of_safety_pct": mos, "fundamentals": bool(fund), "has_thesis": bool(thesis),
        "technical": technical if technical and "error" not in technical else None,
        "profile_complete": DE.profile_completeness(prof)["complete"],
        "horizonte": prof.get("horizonte_anios"),
        "next_earnings": fund.get("next_earnings_date"),
    }
    decision = DE.evaluate_position(ctx)

    # Formato del Módulo 14
    report = {
        "ticker": tk, "empresa": (pos or {}).get("name") or tk, "fecha_hora": D.now(),
        "precio_actual": {"valor": price, "estado": price_st,
                          "fuente": price_row["source"] if price_row else (pos or {}).get("source"),
                          "asof": price_row["asof"] if price_row else None},
        "cantidad": ctx["qty"], "valor_total": ctx["market_value"], "costo_promedio": ctx["avg_cost"],
        "resultado": ctx["unrealized_pl"], "peso_en_cartera_pct": weight,
        "calidad_de_datos": {"fundamentales": bool(fund), "fundamentales_fuente": frow["source"] if frow else None,
                             "fundamentales_asof": frow["asof"] if frow else None,
                             "faltantes": fscores.get("missing", []) + mult.get("missing", []) + scen.get("faltantes", [])},
        "analisis_fundamental": fscores, "multiplos": mult, "valoracion": scen,
        "situacion_tecnica": technical,
        "decision": decision,
        "proxima_revision": body.get("proxima_revision") or "al publicar próximos resultados o en 90 días",
        "disclaimer": DISCLAIMER,
    }
    cur = conn.execute("INSERT INTO decisions (user_id, ticker, proposal, created_at) VALUES (?,?,?,?)",
                       (uid, tk, json.dumps({"decision": decision["decision_propuesta"],
                                             "confianza": decision["nivel_confianza"], "peso": weight,
                                             "margen_seguridad": mos,
                                             "argumentos": decision["argumentos"],
                                             "precio_estado": price_st, "precio_fuente": price_row["source"],
                                             "precio_asof": price_row["asof"],
                                             "fecha_analisis": report["fecha_hora"]}, ensure_ascii=False), D.now()))
    report["decision_id"] = cur.lastrowid
    return report


@router.post("/api/decisions/{did}/record")
def record_decision(did: int, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Módulo 15: registra la decisión del usuario. NUNCA ejecuta la operación."""
    row = conn.execute("SELECT * FROM decisions WHERE id=? AND user_id=?", (did, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Decisión no encontrada")
    conn.execute("UPDATE decisions SET user_choice=?, authorized=? WHERE id=?",
                 (body.get("choice"), int(bool(body.get("authorized"))), did))
    return {"ok": True, "detail": "Decisión registrada. La ejecución la realizas tú en tu bróker; "
                                  "ninguna autorización se reutiliza para operaciones futuras."}


@router.get("/api/decisions")
def decisions_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM decisions WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    return {"decisions": [{**dict(r), "proposal": json.loads(r["proposal"])} for r in rows]}


@router.post("/api/decisions/{did}/explain", dependencies=[Depends(bloquear_en_modo_plan)])
def decision_explain(did: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT proposal FROM decisions WHERE id=? AND user_id=?", (did, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Decisión no encontrada")
    try:
        proposal = json.loads(row["proposal"])
        if not isinstance(proposal, dict) or not isinstance(proposal.get("argumentos"), list) or not proposal["argumentos"]:
            raise ValueError("sin argumentos")
        report = {"decision_propuesta": proposal.get("decision"),
                  "nivel_confianza": proposal.get("confianza"),
                  **{key: proposal.get(key) for key in ("argumentos", "precio_estado", "precio_fuente",
                                                       "precio_asof", "fecha_analisis")}}
        RV.required_text(report["decision_propuesta"], "decision_propuesta", 40)
        if report["decision_propuesta"] not in RV.ACTIONS:
            raise RV.ReviewError("Decisión inválida")
        for key in RV.REPORT_FIELDS:
            if key == "argumentos":
                RV.text_list(report[key], key, 10, 1000)
            elif key != "decision_propuesta":
                RV.text(report[key], key, 1000)
    except (ValueError, TypeError, RV.ReviewError) as exc:
        raise HTTPException(400, "Decisión guardada sin argumentos válidos para explicar") from exc
    try:
        return RV.explain(report)
    except RV.ReviewError as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------- ¿Compro o vendo? (evaluación de una operación concreta) ----------

def _mercado_hoy():
    """Pulso de mercado resumido; si la red falla, None (nunca rompe la evaluación)."""
    try:
        return MP.resumen_pulse(MP.cached_pulse())
    except Exception:
        return None


@router.post("/api/trade_check")
def trade_check(body: TradeCheckIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Evalúa una operación concreta: precio vivo, pesos antes/después, límites,
    motor determinista y fundamentales. Nunca ejecuta ni autoriza la operación."""
    tk = body.ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk):
        raise HTTPException(400, "Ticker inválido")
    if not math.isfinite(body.amount_usd) or body.amount_usd <= 0:
        raise HTTPException(400, "El monto debe ser un número positivo y finito")
    amount = body.amount_usd

    # Modo plan: con el ETF bajo la meta, una compra de acción individual se
    # responde de forma determinista y sin red — no se descarga precio ni se
    # calcula valoración, y no queda decisión registrada.
    mp = MARC.modo_plan_estado(conn, uid)
    if mp["activo"] and body.side == "comprar" and tk not in SB.ETF_META:
        e = MARC.estado_plan(conn, uid)
        target = e["etf_target_pct"]
        plan = BR.regla_plan(tickers=[tk], lado="comprar", meta_pct=target,
                             valor_etf=e["valor_etf_usd"], valor_base=e["valor_base_usd"],
                             monto_usd=amount, delta_base=amount)
        if plan["aplica"] and not plan["cumple"]:
            pct = (f"{plan['etf_pct_antes']:g} %" if plan["etf_pct_antes"] is not None
                   else "sin dato")
            plan["aviso"] = (f"ETF en {pct} de tu meta de {target:g} %: por la regla "
                             "del plan el próximo dinero va al ETF.")
        plan["faltan_usd"] = BR.brecha(valor_base=e["valor_base_usd"] or 0.0,
                                      valor_etf=e["valor_etf_usd"] or 0.0,
                                      meta_pct=target)["brecha_usd"]
        return {"operacion": body.side, "ticker": tk, "monto_usd": amount,
                "modo_plan": mp, "plan": plan, "bloqueado_por_plan": True,
                "cumple_limites": False,
                "limites": [{"limite": "Meta ETF del plan", "valor": plan["etf_pct_antes"],
                             "maximo": target, "cumple": False}],
                "etf_plan": e["etf_plan"], "decision_id": None, "fecha": D.now(),
                "nota": "Modo plan: con el ETF bajo su meta, el próximo dinero va al ETF "
                        "del plan. No se descargó precio ni se calculó valoración."}

    # Precio vivo del ticker y de todas las posiciones (cada cotización queda guardada).
    for t in sorted({p["ticker"] for p in enrich_positions(conn, uid)} | {tk}):
        try:
            store_quote(conn, {**MD.fetch_quote(t), "ticker": t})
        except MD.MarketDataError as e:
            if t == tk:
                raise HTTPException(400, f"No se pudo obtener el precio de {tk}: {e}. "
                                         "Ingresa un precio manual en Cartera › Herramientas avanzadas.") from e

    positions = enrich_positions(conn, uid)
    pos = next((p for p in positions if p["ticker"] == tk), None)
    pos_value = (pos["market_value"] or 0) if pos else 0.0
    if body.side == "vender":
        if pos is None or pos_value <= 0:
            raise HTTPException(400, f"No tienes {tk} en tu cartera.")
        if amount > pos_value + 0.01:
            raise HTTPException(400, f"Solo tienes $ {pos_value:.2f} en {tk}.")

    # En modo plan (venta de acción o compra del ETF del plan) no se descarga
    # nada más: sin SEC ni histórico, y las secciones de valoración quedan None.
    en_modo_plan = mp["activo"]
    fundamentales_nota = None
    if not en_modo_plan and not conn.execute(
            "SELECT 1 FROM fundamentals WHERE user_id=? AND ticker=?",
            (uid, tk)).fetchone():
        try:
            _sec_fundamentals(tk, conn, uid)
        except SEC.SecDataError as e:
            fundamentales_nota = e.detail

    report = _analysis_report(tk, {"assumptions": body.assumptions or {}}, uid, conn,
                              completo=not en_modo_plan)
    price = report["precio_actual"]["valor"]
    cash_row = conn.execute("SELECT amount FROM cash WHERE user_id=?", (uid,)).fetchone()
    efectivo_antes = cash_row["amount"] if cash_row else 0.0
    total_antes = sum(p["market_value"] or 0 for p in positions) + efectivo_antes
    acciones = round(amount / price, 6)
    if body.side == "comprar":
        deposito = round(max(0.0, amount - efectivo_antes), 2)
        efectivo_despues = efectivo_antes + deposito - amount  # efectivo tras depositar lo justo
        valor_despues = pos_value + amount
        total_despues = total_antes + deposito
        efectivo_suficiente = deposito == 0
    else:
        efectivo_despues = efectivo_antes + amount
        deposito = 0.0
        valor_despues = pos_value - amount
        total_despues = total_antes
        efectivo_suficiente = True
    peso_antes = round(pos_value / total_antes * 100, 2) if total_antes else None
    peso_despues = round(valor_despues / total_despues * 100, 2) if total_despues else None

    limits = CU.limites_efectivos(conn, uid)
    sector = (pos or {}).get("sector") or RK.KNOWN_SECTORS.get(tk, "sin clasificar")
    sector_value = valor_despues + sum(
        p["market_value"] or 0 for p in positions if p["ticker"] != tk
        and (p.get("sector") or RK.KNOWN_SECTORS.get(p["ticker"], "sin clasificar")) == sector)
    sector_pct = round(sector_value / total_despues * 100, 2) if total_despues else None
    # Regla del plan, fuente única en brecha.py (la misma que usa el chat):
    # con el ETF bajo su meta, el próximo dinero va al ETF. R1′ evalúa el
    # estado posterior; es vinculante vía el check meta_etf dentro de limites.
    # Solo ETF de índice amplio VERIFICADOS cuentan para la meta: un ETF sin
    # verificar no puede aflojar la regla y comprar QQQ no diversifica.
    valor_etf = SB.etf_meta_value(positions)
    valor_base = sum(p["market_value"] or 0 for p in positions)
    target = D.get_setting(conn, uid, "etf_target_pct", SB.SETTINGS_DEFAULTS["etf_target_pct"])
    plan = BR.regla_plan(tickers=[tk], lado=body.side, meta_pct=target,
                         valor_etf=valor_etf, valor_base=valor_base,
                         monto_usd=amount,
                         delta_base=amount if body.side == "comprar" else -amount)
    if plan["aplica"] and not plan["cumple"] and body.side == "comprar":
        pct = (f"{plan['etf_pct_antes']:g} %" if plan["etf_pct_antes"] is not None
               else "sin dato")
        plan["aviso"] = (f"ETF en {pct} de tu meta de {target:g} %: por la regla "
                         "del plan el próximo dinero va al ETF.")
    plan["faltan_usd"] = BR.brecha(valor_base=valor_base, valor_etf=valor_etf,
                                  meta_pct=target)["brecha_usd"]

    # Los ETF de índice amplio del plan quedan exentos de los límites por
    # empresa y por sector: la meta puede obligarlos a superar el 25 %. QQQ
    # y DIA NO están exentos: concentran megacaps y no cumplen la meta.
    lim_checks = []
    if tk not in SB.ETF_META:
        lim_checks.append(
            {"limite": "Máximo por empresa", "valor": peso_despues, "maximo": limits["max_position_pct"],
             "cumple": peso_despues is not None and peso_despues <= limits["max_position_pct"]})
    # Comprar el ETF del plan es lo que la regla manda: con una cartera chica,
    # el aporte supera el 10 % del total y el límite contradiría al plan
    # (VA-16). Vender ETF sí pasa por el límite: es el impulso a frenar.
    if not (body.side == "comprar" and tk in SB.ETF_META):
        lim_checks.append(
            {"limite": "Máximo por operación",
             "valor": round(amount / total_antes * 100, 2) if total_antes else None,
             "maximo": limits["max_trade_pct"],
             "cumple": bool(total_antes) and amount / total_antes * 100 <= limits["max_trade_pct"]})
    lim_checks.append(
        {"limite": "Reserva mínima de efectivo", "valor": round(efectivo_despues, 2),
         "maximo": limits["min_cash_reserve"], "cumple": efectivo_despues >= limits["min_cash_reserve"]})
    if tk not in SB.ETF_META:
        lim_checks.append(
            {"limite": "Máximo por sector", "valor": sector_pct, "maximo": limits["max_sector_pct"],
             "cumple": sector_pct is not None and sector_pct <= limits["max_sector_pct"]})
    if body.side == "comprar" and plan["aplica"]:
        lim_checks.append(
            {"limite": "Meta ETF del plan",
             "valor": plan["etf_pct_despues"] if plan["regla"] == "R1'" else plan["etf_pct_antes"],
             "maximo": target, "cumple": plan["cumple"]})
    cumple_limites = all(c["cumple"] for c in lim_checks)

    scen = report["valoracion"]
    tec = report["situacion_tecnica"] or {}
    fund_row = conn.execute("SELECT data, source, asof FROM fundamentals WHERE user_id=? AND ticker=?",
                            (uid, tk)).fetchone()
    fund_data = json.loads(fund_row["data"]) if fund_row else None
    numeric_keys = [k for k, _ in AN.FUND_FIELDS if k not in AN.TEXT_FUND_FIELDS]
    prof = CU.perfil_efectivo(conn, uid)
    operacion = {
        "operacion": body.side, "ticker": tk, "monto_usd": amount,
        "precio": {"valor": price, "fuente": report["precio_actual"]["fuente"],
                   "asof": report["precio_actual"]["asof"]},
        "acciones_aprox": acciones,
        "efectivo_antes": round(efectivo_antes, 2), "efectivo_despues": round(efectivo_despues, 2),
        "deposito_necesario": deposito,
        "peso_antes_pct": peso_antes, "peso_despues_pct": peso_despues,
        "total_antes": round(total_antes, 2), "total_despues": round(total_despues, 2),
        "limites": lim_checks, "cumple_limites": cumple_limites,
        "plan": plan,
        "motor": {"propuesta": report["decision"]["decision_propuesta"],
                  "confianza": report["decision"]["nivel_confianza"],
                  "argumentos": report["decision"]["argumentos"]},
        "valoracion": None if en_modo_plan else {
            "calculable": scen["calculable"],
            "valor_base_por_accion": (scen["escenarios"]["base"].get("valor_estimado_por_accion")
                                      if scen["calculable"] else None),
            "margen_seguridad_base_pct": (scen["escenarios"]["base"].get("margen_de_seguridad_pct")
                                          if scen["calculable"] else None)},
        "multiplos": None if en_modo_plan else report["multiplos"]["multiples"],
        "fundamentales": (None if en_modo_plan else
                          ({k: fund_data[k] for k in numeric_keys if k in fund_data}
                           | {"fuente": fund_row["source"], "asof": fund_row["asof"]}) if fund_row else None),
        "tecnica": (None if en_modo_plan else
                    ({k: tec[k] for k in ("tendencia", "rsi14", "distancia_a_maximo_pct",
                                          "volatilidad_anualizada_pct") if k in tec}
                     if tec and "error" not in tec else None)),
        "niveles": None if en_modo_plan else (tec.get("niveles") if tec and "error" not in tec else None),
        "mercado_hoy": None if en_modo_plan else _mercado_hoy(),
        "perfil": {k: prof.get(k) for k in DE.RISK_PROFILE_FIELDS},
        "fecha": D.now(),
    }
    row = conn.execute("SELECT proposal FROM decisions WHERE id=? AND user_id=?",
                       (report["decision_id"], uid)).fetchone()
    proposal = json.loads(row["proposal"])
    proposal["operacion_evaluada"] = operacion
    conn.execute("UPDATE decisions SET proposal=? WHERE id=?",
                 (json.dumps(proposal, ensure_ascii=False), report["decision_id"]))
    return {**operacion, "analisis": None if en_modo_plan else report,
            "decision_id": report["decision_id"], "modo_plan": mp, "bloqueado_por_plan": False,
            "fundamentales_nota": fundamentales_nota, "efectivo_suficiente": efectivo_suficiente,
            "nota": "Cálculo sin comisiones de Hapi ni variación del precio de ejecución."}


@router.post("/api/trade_check/{did}/luna", dependencies=[Depends(bloquear_en_modo_plan)])
def trade_check_luna(did: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Segunda opinión de Luna sobre la operación ya evaluada (no cambia nada)."""
    row = conn.execute("SELECT proposal FROM decisions WHERE id=? AND user_id=?", (did, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Decisión no encontrada")
    op = json.loads(row["proposal"]).get("operacion_evaluada")
    if not op:
        raise HTTPException(400, "Evalúa la operación antes de pedir la opinión de Luna.")
    try:
        return RV.trade_opinion(op)
    except RV.ReviewError as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------- Módulo 8: riesgo ----------

@router.get("/api/risk")
def risk_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    missing_value = without_current_value(positions)
    if missing_value:
        return {"error": "Riesgo no calculable: faltan valores vigentes en USD", "sin_precio_vigente": missing_value}
    cash_row = conn.execute("SELECT amount, currency FROM cash WHERE user_id=?", (uid,)).fetchone()
    if cash_unsupported(cash_row):
        return {"error": "Riesgo no calculable: el efectivo no está en USD"}
    limits = CU.limites_efectivos(conn, uid)
    result = RK.portfolio_risk(positions, cash_row["amount"] if cash_row else 0, limits)
    result["estres_por_posicion"] = {p["ticker"]: RK.stress_position(p["market_value"] or 0) for p in positions}
    return result


@router.put("/api/limits")
def limits_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Cuerdas: endurecer aplica ya; aflojar espera 7 días con motivo en el Diario."""
    try:
        res = CU.proponer(conn, uid, body, rules=CU.LIMIT_RULES, setting_key="limits",
                          pending_key=CU.LIMITES_PENDIENTES, nombre="límites",
                          defaults=RK.DEFAULT_LIMITS)
    except CU.CuerdasError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **res, "limits": CU.limites_efectivos(conn, uid)}


@router.delete("/api/limits/pendientes")
def limits_pendientes_delete(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    batch = CU.cancelar(conn, uid, CU.LIMITES_PENDIENTES)
    if batch is None:
        raise HTTPException(404, "No hay cambio de límites pendiente")
    return {"ok": True, "cancelado": batch}


# ---------- Módulo 10: oportunidades ----------

@router.get("/api/candidates")
def candidates_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM candidates WHERE user_id=?", (uid,)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        nums = [v for k in ("calidad", "crecimiento", "valoracion", "margen_seguridad", "solidez") for v in [d.get(k)] if isinstance(v, (int, float))]
        riesgo = d.get("riesgo")
        score = round(sum(nums) / len(nums) - (riesgo or 0) * 0.3, 2) if nums else None
        out.append({**dict(r), "data": d, "ranking_score": score})
    out.sort(key=lambda x: -(x["ranking_score"] or -99))
    return {"candidates": out,
            "nota": "El ranking usa exclusivamente las puntuaciones que tú registraste con su fuente. "
                    "Un activo no se recomienda solo por haber caído o estar en tendencia."}


@router.post("/api/candidates")
def candidate_add(body: CandidateIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if not body.source.strip():
        raise HTTPException(400, "Indica la fuente de tus datos del candidato")
    conn.execute("INSERT INTO candidates (user_id, ticker, name, data, source, created_at) VALUES (?,?,?,?,?,?)",
                 (uid, body.ticker.upper(), body.name, json.dumps(body.data, ensure_ascii=False), body.source, D.now()))
    return {"ok": True}


@router.delete("/api/candidates/{cid}")
def candidate_delete(cid: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("DELETE FROM candidates WHERE id=? AND user_id=?", (cid, uid))
    return {"ok": True}


# ---------- Módulo 11: alertas ----------

@router.get("/api/alerts")
def alerts(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    out = []
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT amount, currency FROM cash WHERE user_id=?", (uid,)).fetchone()
    limits = CU.limites_efectivos(conn, uid)
    missing_value = without_current_value(positions)
    rk = RK.portfolio_risk(positions, cash_row["amount"] if cash_row else 0, limits) \
        if not missing_value and not cash_unsupported(cash_row) else {}
    if missing_value:
        out.append({"type": "cartera_incompleta", "level": "dato_no_verificado",
                    "text": "Sin total ni riesgo fiables: revisa precios y monedas de " + ", ".join(missing_value)})
    if cash_unsupported(cash_row):
        out.append({"type": "moneda_efectivo", "level": "dato_no_verificado",
                    "text": "Riesgo no calculable: registra el efectivo en USD con un cambio verificable"})
    for b in rk.get("incumplimientos", []):
        out.append({"type": "limite_excedido", "level": "riesgo_elevado", "text": b["detalle"]})
    for note in rk.get("correlacion", []):
        out.append({"type": "correlacion", "level": "revision_necesaria", "text": note})
    for p in positions:
        if p["price_status"] in ("desactualizado", "sin_precio", "captura_sin_verificar", "sin_fecha", "fecha_futura", "moneda_incompatible", "precio_invalido"):
            out.append({"type": "dato_no_verificado", "level": "dato_no_verificado",
                        "text": f"{p['ticker']}: precio {p['price_status'].replace('_', ' ')} — actualízalo antes de decidir"})
        price = D.latest_price(conn, p["ticker"])
        if price and price.get("day_change_pct") is not None and abs(price["day_change_pct"]) >= 5:
            out.append({"type": "movimiento_anormal", "level": "revision_necesaria",
                        "text": f"{p['ticker']} se movió {price['day_change_pct']:+.1f}% en la última sesión: revisa si cambió el negocio o solo el precio"})
    today = D.now()[:10]
    for j in conn.execute("SELECT * FROM journal WHERE user_id=? AND review_date<>'' AND review_date<=? AND evaluation IS NULL",
                          (uid, today)).fetchall():
        out.append({"type": "revision_tesis", "level": "accion_pendiente",
                    "text": f"Toca revisar la tesis de {j['ticker'] or 'cartera'} registrada el {j['created_at'][:10]}"})
    for f in conn.execute("SELECT ticker, data FROM fundamentals WHERE user_id=?", (uid,)).fetchall():
        d = json.loads(f["data"])
        if d.get("next_earnings_date") and str(d["next_earnings_date"]) <= today:
            out.append({"type": "resultados", "level": "revision_necesaria",
                        "text": f"{f['ticker']}: la fecha de resultados registrada ({d['next_earnings_date']}) ya pasó — actualiza fundamentales"})
    prof = CU.perfil_efectivo(conn, uid)
    if not DE.profile_completeness(prof)["complete"]:
        out.append({"type": "perfil", "level": "informativa",
                    "text": "Completa tu perfil de inversionista para recibir recomendaciones personalizadas"})
    return {"alerts": out}


# ---------- Módulo 12: diario ----------

@router.get("/api/journal")
def journal_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM journal WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    return {"entries": [{**dict(r), "data": json.loads(r["data"]),
                         "evaluation": json.loads(r["evaluation"]) if r["evaluation"] else None} for r in rows]}


@router.post("/api/journal")
def journal_add(body: JournalIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    required = {"tesis": body.tesis, "riesgos": body.riesgos,
                "condicion_invalidacion": body.condicion_invalidacion}
    missing = [k for k, v in required.items() if not v.strip()]
    if body.action in ("comprar", "vender", "agregar", "reducir") and missing:
        raise HTTPException(400, f"Antes de registrar una operación completa: {', '.join(missing)}")
    data = body.model_dump(exclude={"review_date"})
    cur = conn.execute("INSERT INTO journal (user_id, ticker, action, data, review_date, created_at) VALUES (?,?,?,?,?,?)",
                       (uid, body.ticker.upper(), body.action, json.dumps(data, ensure_ascii=False),
                        body.review_date, D.now()))
    return {"ok": True, "id": cur.lastrowid}


@router.post("/api/journal/{jid}/evaluate")
def journal_evaluate(jid: int, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Evaluación posterior: proceso vs resultado (una buena decisión puede perder dinero)."""
    row = conn.execute("SELECT id FROM journal WHERE id=? AND user_id=?", (jid, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Entrada no encontrada")
    evaluation = {k: body.get(k) for k in
                  ("que_ocurrio", "tesis_correcta", "suerte_o_proceso", "hubo_fomo",
                   "vendio_por_miedo", "leccion")}
    conn.execute("UPDATE journal SET evaluation=? WHERE id=?", (json.dumps(evaluation, ensure_ascii=False), jid))
    return {"ok": True}


@router.post("/api/journal/{jid}/challenge", dependencies=[Depends(bloquear_en_modo_plan)])
def journal_challenge(jid: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT data, ticker, created_at FROM journal WHERE id=? AND user_id=?", (jid, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Entrada no encontrada")
    try:
        entry = json.loads(row["data"])
        if not isinstance(entry, dict):
            raise ValueError("entrada inválida")
        entry = {**entry, "ticker": row["ticker"], "created_at": row["created_at"]}
        RV.required_text(entry.get("tesis"), "tesis", 3000)
        for key in RV.ENTRY_FIELDS:
            if key == "fuentes":
                if isinstance(entry.get(key), list):
                    RV.text_list(entry[key], key, 10, 500)
                else:
                    RV.text(entry.get(key), key, 1000)
            elif key != "tesis":
                RV.text(entry.get(key), key, 1000)
    except (ValueError, TypeError, RV.ReviewError) as exc:
        raise HTTPException(400, "Entrada de diario inválida para revisión") from exc
    try:
        return RV.challenge(entry)
    except RV.ReviewError as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------- Módulo 13: panel ----------

@router.get("/api/dashboard")
def dashboard(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    pf = portfolio(uid, conn)
    rk = risk_get(uid, conn)
    al = alerts(uid, conn)
    theses = conn.execute("SELECT ticker, action, review_date, created_at, evaluation IS NOT NULL done "
                          "FROM journal WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)).fetchall()
    decs = conn.execute("SELECT ticker, proposal, user_choice, created_at FROM decisions WHERE user_id=? ORDER BY id DESC LIMIT 5",
                        (uid,)).fetchall()
    events = []
    for f in conn.execute("SELECT ticker, data FROM fundamentals WHERE user_id=?", (uid,)).fetchall():
        d = json.loads(f["data"])
        if d.get("next_earnings_date"):
            events.append({"ticker": f["ticker"], "evento": "resultados", "fecha": d["next_earnings_date"]})
    data_quality = [{"ticker": p["ticker"], "estado_precio": p["price_status"], "verificada": bool(p["verified"])}
                    for p in pf["positions"]]
    return {"portfolio": pf, "risk": {k: rk.get(k) for k in ("error", "hhi", "nivel_concentracion",
                                                             "diversificacion_efectiva", "sectores",
                                                             "correlacion", "incumplimientos")},
            "alerts": al["alerts"], "eventos": events,
            "tesis_recientes": [dict(t) for t in theses],
            "decisiones_recientes": [{**dict(d), "proposal": json.loads(d["proposal"])} for d in decs],
            "calidad_datos": data_quality, "disclaimer": DISCLAIMER}
