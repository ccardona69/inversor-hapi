"""Inversor Hapi IA — API principal (FastAPI).

Sistema de apoyo a decisiones de inversión: transforma datos con fuente y fecha
en decisiones explicables. No promete rentabilidad, no inventa cifras, no
ejecuta operaciones: siempre propone, muestra riesgos y pide que el usuario
ejecute personalmente en su bróker.
"""
import json
import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db as D
from . import marketdata as MD
from . import analysis as AN
from . import risk as RK
from . import decisions as DE

app = FastAPI(title="Inversor Hapi IA", version="0.1.0")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
D.init_db()

DISCLAIMER = ("Herramienta de apoyo a decisiones con datos aportados por el usuario y fuentes públicas. "
              "No es asesoría financiera regulada ni garantiza rentabilidad.")


def conn_dep():
    conn = D.get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def current_user(request: Request, conn=Depends(conn_dep)) -> int:
    uid = D.session_user(conn, request.cookies.get("session"))
    if uid is None:
        raise HTTPException(401, "No autenticado")
    return uid


# ---------- modelos ----------

class Credentials(BaseModel):
    email: str
    password: str


class PositionIn(BaseModel):
    ticker: str
    name: str = ""
    sector: str = ""
    qty: float
    avg_cost: Optional[float] = None
    invested: Optional[float] = None
    hapi_value: Optional[float] = None
    hapi_pl: Optional[float] = None
    hapi_return_pct: Optional[float] = None
    currency: str = "USD"
    source: str = "manual"
    notes: str = ""


class ManualPrice(BaseModel):
    ticker: str
    price: float
    asof: str
    source: str = "ingreso manual"
    currency: str = "USD"


class FundamentalsIn(BaseModel):
    data: dict
    source: str
    asof: str


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


# ---------- autenticación ----------

@app.post("/api/register")
def register(body: Credentials, response: Response, conn=Depends(conn_dep)):
    if len(body.password) < 8:
        raise HTTPException(400, "Contraseña mínima: 8 caracteres")
    try:
        uid = D.create_user(conn, body.email, body.password)
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Correo ya registrado")
    token = D.create_session(conn, uid)
    D.audit(conn, uid, "registro", body.email)
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return {"ok": True}


@app.post("/api/login")
def login(body: Credentials, response: Response, conn=Depends(conn_dep)):
    uid = D.check_login(conn, body.email, body.password)
    if uid is None:
        raise HTTPException(401, "Credenciales incorrectas")
    token = D.create_session(conn, uid)
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response, conn=Depends(conn_dep)):
    token = request.cookies.get("session")
    if token:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
    return {"user_id": uid, "email": row["email"], "disclaimer": DISCLAIMER}


# ---------- perfil del inversionista ----------

@app.get("/api/profile")
def profile_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    return {"profile": prof, "fields": DE.RISK_PROFILE_FIELDS, **DE.profile_completeness(prof)}


@app.put("/api/profile")
def profile_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    prof.update(body)
    D.set_setting(conn, uid, "risk_profile", prof)
    D.audit(conn, uid, "perfil_actualizado", ", ".join(body.keys()))
    return {"ok": True, **DE.profile_completeness(prof)}


# ---------- Módulo 1: cartera ----------

def position_rows(conn, uid):
    return [dict(r) for r in conn.execute("SELECT * FROM positions WHERE user_id=?", (uid,)).fetchall()]


def enrich_positions(conn, uid):
    """Une posiciones con el último precio; nunca presenta un precio viejo como actual."""
    out = []
    for p in position_rows(conn, uid):
        price = D.latest_price(conn, p["ticker"])
        st = MD.staleness(price["asof"]) if price else {"status": "sin_precio", "usable_as_current": False}
        if price and st["usable_as_current"]:
            mv = round(p["qty"] * price["price"], 2)
            basis = {"precio_usado": price["price"], "fuente": price["source"], "asof": price["asof"]}
        elif p["hapi_value"] is not None:
            mv = p["hapi_value"]
            basis = {"precio_usado": round(p["hapi_value"] / p["qty"], 2) if p["qty"] else None,
                     "fuente": p["source"] + " (valor de la captura, verificar)", "asof": p["created_at"]}
            st = {**st, "status": st["status"] if price else "captura_sin_verificar"}
        else:
            mv, basis = None, {"fuente": "sin precio disponible"}
        pl = round(mv - p["invested"], 2) if mv is not None and p["invested"] else None
        out.append({**p, "market_value": mv, "unrealized_pl": pl,
                    "return_pct": round(pl / p["invested"] * 100, 2) if pl is not None and p["invested"] else None,
                    "price_info": basis, "price_status": st["status"]})
    return out


@app.get("/api/portfolio")
def portfolio(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT * FROM cash WHERE user_id=?", (uid,)).fetchone()
    cash = cash_row["amount"] if cash_row else 0.0
    total_mv = sum(p["market_value"] or 0 for p in positions)
    invested = sum(p["invested"] or 0 for p in positions)
    weights = {p["ticker"]: round((p["market_value"] or 0) / total_mv * 100, 2) for p in positions if total_mv}
    return {
        "positions": positions, "cash": cash,
        "totals": {"invertido": round(invested, 2), "valor_actual": round(total_mv, 2),
                   "resultado": round(total_mv - invested, 2) if invested else None,
                   "rendimiento_pct": round((total_mv / invested - 1) * 100, 2) if invested else None,
                   "pesos_pct": weights},
        "disclaimer": DISCLAIMER,
    }


@app.post("/api/positions")
def position_upsert(body: PositionIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = body.ticker.upper().strip()
    invested = body.invested
    if invested is None and body.avg_cost is not None:
        invested = round(body.qty * body.avg_cost, 2)
    avg = body.avg_cost
    if avg is None and invested and body.qty:
        avg = round(invested / body.qty, 4)
    conn.execute(
        """INSERT INTO positions (user_id, ticker, name, sector, currency, qty, avg_cost, invested,
             hapi_value, hapi_pl, hapi_return_pct, source, notes, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id, ticker) DO UPDATE SET name=excluded.name, sector=excluded.sector,
             qty=excluded.qty, avg_cost=excluded.avg_cost, invested=excluded.invested,
             hapi_value=excluded.hapi_value, hapi_pl=excluded.hapi_pl, hapi_return_pct=excluded.hapi_return_pct,
             source=excluded.source, notes=excluded.notes, updated_at=excluded.updated_at""",
        (uid, tk, body.name, body.sector or RK.KNOWN_SECTORS.get(tk, ""), body.currency, body.qty,
         avg, invested, body.hapi_value, body.hapi_pl, body.hapi_return_pct, body.source, body.notes,
         D.now(), D.now()),
    )
    D.audit(conn, uid, "posicion_guardada", f"{tk} qty={body.qty}")
    return {"ok": True}


@app.delete("/api/positions/{ticker}")
def position_delete(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("DELETE FROM positions WHERE user_id=? AND ticker=?", (uid, ticker.upper()))
    D.audit(conn, uid, "posicion_borrada", ticker)
    return {"ok": True}


@app.put("/api/cash")
def cash_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(user_id) DO UPDATE SET amount=excluded.amount, updated_at=excluded.updated_at",
                 (uid, float(body.get("amount") or 0), body.get("currency", "USD"), D.now()))
    return {"ok": True}


@app.post("/api/seed_hapi")
def seed_hapi(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Carga la cartera que el usuario reportó desde su app Hapi (2026-07-19).
    Queda marcada como 'pendiente de verificación' hasta que el usuario la confirme."""
    src = "Hapi — captura reportada por el usuario el 2026-07-19 (pendiente de verificación)"
    for p in [
        PositionIn(ticker="NVDA", name="NVIDIA", sector=RK.KNOWN_SECTORS["NVDA"], qty=1.54575,
                   invested=335.37, avg_cost=216.96, hapi_value=313.49, hapi_pl=-21.88,
                   hapi_return_pct=-6.52, source=src,
                   notes="Derivados aproximados: verificar redondeos, comisiones e impuestos"),
        PositionIn(ticker="MSFT", name="Microsoft", sector=RK.KNOWN_SECTORS["MSFT"], qty=0.27219,
                   invested=118.44, avg_cost=435.14, hapi_value=107.19, hapi_pl=-11.25,
                   hapi_return_pct=-9.50, source=src,
                   notes="Derivados aproximados: verificar redondeos, comisiones e impuestos"),
    ]:
        position_upsert(p, uid, conn)
    D.audit(conn, uid, "cartera_hapi_cargada", "NVDA + MSFT")
    return {"ok": True, "detail": "Cartera cargada desde tu reporte de Hapi. Ejecuta la validación de datos."}


@app.post("/api/positions/import")
def positions_import(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Importa posiciones desde un archivo que el usuario exportó de su bróker.

    El CSV/Excel se parsea en el navegador y aquí llegan filas ya mapeadas. NUNCA se
    piden credenciales de Hapi ni se conecta a su cuenta: el usuario sube su propio
    archivo. Todo entra marcado 'pendiente de verificación' (verified=0), como el resto.
    """
    rows = body.get("rows") or []
    if not rows:
        raise HTTPException(400, "No hay filas para importar")
    source = "Hapi (CSV exportado por el usuario — pendiente de verificación)"
    importadas, omitidas = [], []
    for r in rows:
        tk = str(r.get("ticker") or "").upper().strip()
        try:
            qty = float(r.get("qty"))
        except (TypeError, ValueError):
            qty = 0.0
        if not tk or qty <= 0:
            omitidas.append({"fila": r, "motivo": "ticker vacío o cantidad no válida"})
            continue
        pin = PositionIn(ticker=tk, name=str(r.get("name") or ""), qty=qty,
                         avg_cost=r.get("avg_cost"), invested=r.get("invested"), source=source)
        position_upsert(pin, uid, conn)
        importadas.append(tk)
    D.audit(conn, uid, "cartera_importada_csv", f"{len(importadas)} importadas, {len(omitidas)} omitidas")
    return {"ok": True, "importadas": importadas, "omitidas": omitidas,
            "detail": f"{len(importadas)} posición(es) importada(s), marcadas «pendiente de verificación». "
                      "Revísalas y confírmalas en la validación de datos."}


# ---------- Módulo 2: validación ----------

@app.get("/api/validate")
def validate(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    report = []
    for p in position_rows(conn, uid):
        confirmed, calculated, pending, issues = [], [], [], []
        confirmed.append(f"Cantidad: {p['qty']} (fuente: {p['source']})")
        if p["invested"] and p["qty"]:
            derived_avg = p["invested"] / p["qty"]
            calculated.append(f"Costo promedio derivado: {derived_avg:.2f} {p['currency']}/acción")
            if p["avg_cost"] and abs(derived_avg - p["avg_cost"]) / p["avg_cost"] > 0.01:
                issues.append(f"Costo promedio registrado ({p['avg_cost']}) difiere del derivado ({derived_avg:.2f}) en más de 1%")
        if p["hapi_value"] is not None and p["hapi_pl"] is not None and p["invested"]:
            implied_invested = p["hapi_value"] - p["hapi_pl"]
            if abs(implied_invested - p["invested"]) > max(0.5, p["invested"] * 0.01):
                issues.append(f"Invertido registrado ({p['invested']}) vs valor−P/L de Hapi ({implied_invested:.2f}): revisar comisiones/redondeo")
            else:
                calculated.append(f"Invertido coherente con valor−P/L de Hapi ({implied_invested:.2f})")
        if p["hapi_return_pct"] is not None and p["hapi_pl"] is not None and p["invested"]:
            derived_ret = p["hapi_pl"] / p["invested"] * 100
            if abs(derived_ret - p["hapi_return_pct"]) > 0.6:
                issues.append(f"Rendimiento de Hapi ({p['hapi_return_pct']}%) vs derivado ({derived_ret:.2f}%): "
                              "confirmar si es del día o del periodo completo")
            else:
                calculated.append(f"Rendimiento derivado {derived_ret:.2f}% coincide con Hapi ({p['hapi_return_pct']}%)")
        price = D.latest_price(conn, p["ticker"])
        if price:
            st = MD.staleness(price["asof"])
            confirmed.append(f"Precio {price['price']} {price['currency']} — {price['source']} ({price['asof']}, {st['status']})")
            if p["hapi_value"] and p["qty"]:
                implied = p["hapi_value"] / p["qty"]
                diff = (price["price"] / implied - 1) * 100
                if abs(diff) > 3:
                    issues.append(f"Precio implícito de la captura ({implied:.2f}) difiere {diff:+.1f}% del precio de mercado: la captura puede ser de otra fecha")
        else:
            pending.append("Precio de mercado: actualízalo (botón Actualizar precios) o ingrésalo manualmente")
        pending.append("Comisiones e impuestos de compra: no registrados (afectan el costo real)")
        if not p["verified"]:
            pending.append("Confirmación del usuario de cantidades y montos")
        report.append({"ticker": p["ticker"], "confirmados": confirmed, "calculados": calculated,
                       "pendientes": pending, "inconsistencias": issues})
    return {"report": report}


@app.post("/api/positions/{ticker}/verify")
def verify_position(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("UPDATE positions SET verified=1, updated_at=? WHERE user_id=? AND ticker=?",
                 (D.now(), uid, ticker.upper()))
    D.audit(conn, uid, "posicion_verificada", ticker)
    return {"ok": True}


# ---------- Módulo 3: precios ----------

@app.post("/api/prices/refresh")
def prices_refresh(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    results, errors = [], []
    tickers = {p["ticker"] for p in position_rows(conn, uid)}
    tickers |= {r["ticker"] for r in conn.execute("SELECT ticker FROM candidates WHERE user_id=?", (uid,)).fetchall()}
    for tk in sorted(tickers):
        try:
            q = MD.fetch_quote(tk)
            conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, day_change_pct, created_at) VALUES (?,?,?,?,?,?,?)",
                         (tk, q["price"], q["currency"], q["asof"], q["source"], q["day_change_pct"], D.now()))
            results.append(q)
        except MD.MarketDataError as e:
            errors.append({"ticker": tk, "error": str(e)})
    D.audit(conn, uid, "precios_actualizados", f"{len(results)} ok, {len(errors)} errores")
    return {"updated": results, "errors": errors}


@app.post("/api/prices/manual")
def price_manual(body: ManualPrice, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, created_at) VALUES (?,?,?,?,?,?)",
                 (body.ticker.upper(), body.price, body.currency, body.asof, body.source, D.now()))
    D.audit(conn, uid, "precio_manual", f"{body.ticker} {body.price}")
    return {"ok": True}


# ---------- fundamentales ----------

@app.get("/api/fundamentals/{ticker}")
def fundamentals_get(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT * FROM fundamentals WHERE user_id=? AND ticker=?", (uid, ticker.upper())).fetchone()
    return {"ticker": ticker.upper(),
            "fields": AN.FUND_FIELDS,
            "fundamentals": json.loads(row["data"]) if row else {},
            "source": row["source"] if row else None, "asof": row["asof"] if row else None,
            "staleness": MD.staleness(row["asof"]) if row else None}


@app.put("/api/fundamentals/{ticker}")
def fundamentals_put(ticker: str, body: FundamentalsIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if not body.source.strip() or not body.asof.strip():
        raise HTTPException(400, "Fuente y fecha del dato son obligatorias")
    conn.execute("INSERT INTO fundamentals (user_id, ticker, data, source, asof, created_at) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT(user_id, ticker) DO UPDATE SET data=excluded.data, source=excluded.source, "
                 "asof=excluded.asof, created_at=excluded.created_at",
                 (uid, ticker.upper(), json.dumps(body.data, ensure_ascii=False), body.source, body.asof, D.now()))
    D.audit(conn, uid, "fundamentales_guardados", ticker)
    return {"ok": True}


# ---------- Módulos 4-7 y 14: análisis y recomendación ----------

@app.post("/api/analysis/{ticker}")
def analyze(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = ticker.upper()
    pos = next((p for p in enrich_positions(conn, uid) if p["ticker"] == tk), None)
    frow = conn.execute("SELECT * FROM fundamentals WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
    fund = json.loads(frow["data"]) if frow else {}
    price_row = D.latest_price(conn, tk)
    price = price_row["price"] if price_row else (pos["price_info"].get("precio_usado") if pos else None)
    price_st = MD.staleness(price_row["asof"]).get("status") if price_row else (pos["price_status"] if pos else "sin_precio")
    if price is None:
        raise HTTPException(400, "Sin precio disponible: actualiza precios o ingresa uno manual")

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
    positions = enrich_positions(conn, uid)
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
                                             "margen_seguridad": mos}, ensure_ascii=False), D.now()))
    report["decision_id"] = cur.lastrowid
    D.audit(conn, uid, "analisis_generado", f"{tk} -> {decision['decision_propuesta']}")
    return report


@app.post("/api/decisions/{did}/record")
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


@app.get("/api/decisions")
def decisions_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM decisions WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    return {"decisions": [{**dict(r), "proposal": json.loads(r["proposal"])} for r in rows]}


# ---------- Módulo 8: riesgo ----------

@app.get("/api/risk")
def risk_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT amount FROM cash WHERE user_id=?", (uid,)).fetchone()
    limits = D.get_setting(conn, uid, "limits", {}) or {}
    result = RK.portfolio_risk(positions, cash_row["amount"] if cash_row else 0, limits)
    result["estres_por_posicion"] = {p["ticker"]: RK.stress_position(p["market_value"] or 0) for p in positions}
    return result


@app.put("/api/limits")
def limits_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    limits = {**(D.get_setting(conn, uid, "limits", {}) or {}), **body}
    D.set_setting(conn, uid, "limits", limits)
    D.audit(conn, uid, "limites_actualizados", json.dumps(body)[:200])
    return {"ok": True, "limits": {**RK.DEFAULT_LIMITS, **limits}}


# ---------- Módulo 9: simulador ----------

@app.post("/api/simulate")
def simulate(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT amount FROM cash WHERE user_id=?", (uid,)).fetchone()
    return DE.simulate(positions, cash_row["amount"] if cash_row else 0,
                       body.get("changes") or {}, body.get("trades") or [])


# ---------- Módulo 10: oportunidades ----------

@app.get("/api/candidates")
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


@app.post("/api/candidates")
def candidate_add(body: CandidateIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if not body.source.strip():
        raise HTTPException(400, "Indica la fuente de tus datos del candidato")
    conn.execute("INSERT INTO candidates (user_id, ticker, name, data, source, created_at) VALUES (?,?,?,?,?,?)",
                 (uid, body.ticker.upper(), body.name, json.dumps(body.data, ensure_ascii=False), body.source, D.now()))
    D.audit(conn, uid, "candidato_agregado", body.ticker)
    return {"ok": True}


@app.delete("/api/candidates/{cid}")
def candidate_delete(cid: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("DELETE FROM candidates WHERE id=? AND user_id=?", (cid, uid))
    return {"ok": True}


# ---------- Módulo 11: alertas ----------

@app.get("/api/alerts")
def alerts(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    out = []
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT amount FROM cash WHERE user_id=?", (uid,)).fetchone()
    limits = D.get_setting(conn, uid, "limits", {}) or {}
    rk = RK.portfolio_risk(positions, cash_row["amount"] if cash_row else 0, limits)
    for b in rk.get("incumplimientos", []):
        out.append({"type": "limite_excedido", "level": "riesgo_elevado", "text": b["detalle"]})
    for note in rk.get("correlacion", []):
        out.append({"type": "correlacion", "level": "revision_necesaria", "text": note})
    for p in positions:
        if p["price_status"] in ("desactualizado", "sin_precio", "captura_sin_verificar", "sin_fecha"):
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

@app.get("/api/journal")
def journal_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM journal WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    return {"entries": [{**dict(r), "data": json.loads(r["data"]),
                         "evaluation": json.loads(r["evaluation"]) if r["evaluation"] else None} for r in rows]}


@app.post("/api/journal")
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


@app.post("/api/journal/{jid}/evaluate")
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


# ---------- Módulo 13: panel ----------

@app.get("/api/dashboard")
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
    return {"portfolio": pf, "risk": {k: rk.get(k) for k in ("hhi", "nivel_concentracion", "diversificacion_efectiva",
                                                             "sectores", "correlacion", "incumplimientos")},
            "alerts": al["alerts"], "eventos": events,
            "tesis_recientes": [dict(t) for t in theses],
            "decisiones_recientes": [{**dict(d), "proposal": json.loads(d["proposal"])} for d in decs],
            "calidad_datos": data_quality, "disclaimer": DISCLAIMER}


# ---------- configuración ----------

@app.get("/api/settings")
def settings_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return {"limits": {**RK.DEFAULT_LIMITS, **(D.get_setting(conn, uid, "limits", {}) or {})}}


@app.get("/api/audit")
def audit_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM audit_log WHERE user_id=? ORDER BY id DESC LIMIT 200", (uid,)).fetchall()
    return {"log": [dict(r) for r in rows]}


@app.post("/api/settings/delete_all")
def delete_all(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if body.get("confirm") != "ELIMINAR":
        raise HTTPException(400, 'Escribe "ELIMINAR" en confirm')
    for t in ("positions", "trades", "fundamentals", "journal", "decisions", "candidates",
              "alerts", "settings", "audit_log", "cash"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados"}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
