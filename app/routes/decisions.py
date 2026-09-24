"""Módulos 4-15: análisis y decisión, riesgo, simulador, oportunidades, alertas,
diario de inversión y panel. El motor de decisión es determinista; la IA solo
explica o cuestiona, nunca propone por su cuenta."""
import json
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import ai_review as RV
from .. import analysis as AN
from .. import db as D
from .. import decisions as DE
from .. import marketdata as MD
from .. import risk as RK
from ..deps import DISCLAIMER, conn_dep, current_user
from .portfolio import cash_unsupported, enrich_positions, portfolio, without_current_value

router = APIRouter()


class JournalIn(BaseModel):
    ticker: str = ""
    action: str = "revision"
    motivo: str = ""
    tesis: str = ""
    precio: Optional[float] = None
    valoracion: str = ""
    horizonte: str = ""
    catalizadores: str = ""
    riesgos: str = ""
    condiciones_salida: str = ""
    condicion_invalidacion: str = ""
    perdida_tolerable: str = ""
    tamano_posicion: str = ""
    estado_emocional: str = ""
    fuentes: str = ""
    review_date: str = ""


class CandidateIn(BaseModel):
    ticker: str
    name: str = ""
    source: str
    data: dict  # calidad, crecimiento, valoracion, margen_seguridad, solidez, riesgo (0-10), tesis, catalizadores, condicion_entrada, condicion_espera, condicion_invalidacion


# ---------- Módulos 4-7 y 14: análisis y recomendación ----------

@router.post("/api/analysis/{ticker}")
def analyze(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = ticker.upper()
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
    try:
        hist = MD.fetch_history(tk)
        technical = MD.technical_summary(hist["rows"])
        technical["fuente"] = hist["source"]
        technical["obtenido"] = hist["fetched_at"]
    except MD.MarketDataError as e:
        technical = {"error": str(e)}

    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    limits = D.get_setting(conn, uid, "limits", {}) or {}
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
    D.audit(conn, uid, "analisis_generado", f"{tk} -> {decision['decision_propuesta']}")
    return report


@router.post("/api/decisions/{did}/record")
def record_decision(did: int, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Módulo 15: registra la decisión del usuario. NUNCA ejecuta la operación."""
    row = conn.execute("SELECT * FROM decisions WHERE id=? AND user_id=?", (did, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Decisión no encontrada")
    conn.execute("UPDATE decisions SET user_choice=?, authorized=? WHERE id=?",
                 (body.get("choice"), int(bool(body.get("authorized"))), did))
    D.audit(conn, uid, "decision_registrada", f"#{did} {body.get('choice')}")
    return {"ok": True, "detail": "Decisión registrada. La ejecución la realizas tú en tu bróker; "
                                  "ninguna autorización se reutiliza para operaciones futuras."}


@router.get("/api/decisions")
def decisions_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM decisions WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    return {"decisions": [{**dict(r), "proposal": json.loads(r["proposal"])} for r in rows]}


@router.post("/api/decisions/{did}/explain")
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
    limits = D.get_setting(conn, uid, "limits", {}) or {}
    result = RK.portfolio_risk(positions, cash_row["amount"] if cash_row else 0, limits)
    result["estres_por_posicion"] = {p["ticker"]: RK.stress_position(p["market_value"] or 0) for p in positions}
    return result


@router.put("/api/limits")
def limits_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    limits = {**(D.get_setting(conn, uid, "limits", {}) or {}), **body}
    D.set_setting(conn, uid, "limits", limits)
    D.audit(conn, uid, "limites_actualizados", json.dumps(body)[:200])
    return {"ok": True, "limits": {**RK.DEFAULT_LIMITS, **limits}}


# ---------- Módulo 9: simulador ----------

@router.post("/api/simulate")
def simulate(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    missing_value = without_current_value(positions)
    if missing_value:
        raise HTTPException(400, "Simulación no calculable: actualiza valores en USD de " + ", ".join(missing_value))
    cash_row = conn.execute("SELECT amount, currency FROM cash WHERE user_id=?", (uid,)).fetchone()
    if cash_unsupported(cash_row):
        raise HTTPException(400, "Simulación no calculable: el efectivo no está en USD")
    return DE.simulate(positions, cash_row["amount"] if cash_row else 0,
                       body.get("changes") or {}, body.get("trades") or [])


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
    D.audit(conn, uid, "candidato_agregado", body.ticker)
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
    limits = D.get_setting(conn, uid, "limits", {}) or {}
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
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
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
    required = {"motivo": body.motivo, "tesis": body.tesis, "riesgos": body.riesgos,
                "condicion_invalidacion": body.condicion_invalidacion}
    missing = [k for k, v in required.items() if not v.strip()]
    if body.action in ("comprar", "vender", "agregar", "reducir") and missing:
        raise HTTPException(400, f"Antes de registrar una operación completa: {', '.join(missing)}")
    data = body.model_dump(exclude={"review_date"})
    cur = conn.execute("INSERT INTO journal (user_id, ticker, action, data, review_date, created_at) VALUES (?,?,?,?,?,?)",
                       (uid, body.ticker.upper(), body.action, json.dumps(data, ensure_ascii=False),
                        body.review_date, D.now()))
    D.audit(conn, uid, "diario_registrado", f"{body.ticker} {body.action}")
    return {"ok": True, "id": cur.lastrowid}


@router.post("/api/journal/{jid}/evaluate")
def journal_evaluate(jid: int, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Evaluación posterior: proceso vs resultado (una buena decisión puede perder dinero)."""
    row = conn.execute("SELECT id FROM journal WHERE id=? AND user_id=?", (jid, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Entrada no encontrada")
    evaluation = {k: body.get(k) for k in
                  ("que_ocurrio", "tesis_correcta", "tamano_adecuado", "hubo_fomo", "compro_tras_subida",
                   "promedio_sin_justificacion", "vendio_por_miedo", "ignoro_valoracion", "suerte_o_proceso", "leccion")}
    conn.execute("UPDATE journal SET evaluation=? WHERE id=?", (json.dumps(evaluation, ensure_ascii=False), jid))
    D.audit(conn, uid, "diario_evaluado", f"#{jid}")
    return {"ok": True}


@router.post("/api/journal/{jid}/challenge")
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
