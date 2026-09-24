"""Inversor Hapi IA — API principal (FastAPI).

Sistema de apoyo a decisiones de inversión: transforma datos con fuente y fecha
en decisiones explicables. No promete rentabilidad, no inventa cifras, no
ejecuta operaciones: siempre propone, muestra riesgos y pide que el usuario
ejecute personalmente en su bróker.
"""
import hashlib
import json
import math
import os
import secrets
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import db as D
from . import marketdata as MD
from . import photosync as PS
from . import ai_assistant as AI
from . import analysis as AN
from . import risk as RK
from . import decisions as DE
from . import fundsync as FS
from . import tradesync as TS
from . import ai_review as RV
from . import ai_provider as AP

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

class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=600)


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
            if (p["currency"] or "USD").upper() != "USD" or (price["currency"] or "USD").upper() != "USD":
                st = {**st, "status": "moneda_incompatible", "usable_as_current": False}
            elif price["price"] is None or not math.isfinite(price["price"]) or price["price"] <= 0:
                st = {**st, "status": "precio_invalido", "usable_as_current": False}
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
        pl = round(mv - p["invested"], 2) if st["usable_as_current"] and p["invested"] is not None else None
        out.append({**p, "market_value": mv, "unrealized_pl": pl,
                    "return_pct": round(pl / p["invested"] * 100, 2) if pl is not None and p["invested"] else None,
                    "price_info": basis, "price_status": st["status"]})
    return out


def without_current_value(positions):
    return [p["ticker"] for p in positions
            if p["market_value"] is None or p["price_status"] not in ("actual", "reciente")
            or (p["currency"] or "USD").upper() != "USD"]


def cash_unsupported(cash_row):
    return bool(cash_row and (cash_row["currency"] or "USD").upper() != "USD")


@app.get("/api/portfolio")
def portfolio(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    positions = enrich_positions(conn, uid)
    cash_row = conn.execute("SELECT * FROM cash WHERE user_id=?", (uid,)).fetchone()
    cash = None if cash_unsupported(cash_row) else (cash_row["amount"] if cash_row else 0.0)
    missing_value = without_current_value(positions)
    missing_cost = [p["ticker"] for p in positions if p["invested"] is None]
    total_mv = sum(p["market_value"] or 0 for p in positions)
    invested = sum(p["invested"] or 0 for p in positions)
    complete = not missing_value and not missing_cost
    weights = {p["ticker"]: round(p["market_value"] / total_mv * 100, 2)
               for p in positions} if not missing_value and total_mv else {}
    return {
        "positions": positions, "cash": cash,
        "cash_currency": cash_row["currency"] if cash_row else "USD",
        "totals": {"invertido": round(invested, 2) if not missing_cost else None,
                   "valor_actual": round(total_mv, 2) if not missing_value else None,
                   "resultado": round(total_mv - invested, 2) if complete and invested else None,
                   "rendimiento_pct": round((total_mv / invested - 1) * 100, 2) if complete and invested else None,
                   "pesos_pct": weights, "sin_precio_vigente": missing_value, "sin_costo": missing_cost},
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
             source=excluded.source, notes=excluded.notes, verified=0,
             updated_at=excluded.updated_at""",
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
    if (body.get("currency") or "USD").upper() != "USD":
        raise HTTPException(400, "Solo se admite efectivo en USD; no hay tipo de cambio verificado")
    try:
        amount = float(body.get("amount") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "El efectivo debe ser un número finito")
    if not math.isfinite(amount):
        raise HTTPException(400, "El efectivo debe ser un número finito")
    conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(user_id) DO UPDATE SET amount=excluded.amount, "
                 "currency=excluded.currency, updated_at=excluded.updated_at",
                 (uid, amount, "USD", D.now()))
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


# ---------- sincronización con Hapi por foto (IA de visión) ----------

@app.get("/api/hapi/photo/status")
def photo_status(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return PS.config_status()


@app.post("/api/hapi/photo/analyze")
def photo_analyze(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Analiza la captura con el modelo de visión y devuelve las filas detectadas.
    NO guarda nada: la IA propone, el usuario revisa y confirma en /save."""
    image = (body.get("image_b64") or "").strip()
    if image.startswith("data:"):
        _, _, image = image.partition(",")
    if not image:
        raise HTTPException(400, "No se recibió ninguna imagen")
    try:
        result = PS.analyze(image, body.get("mime") or "image/jpeg")
    except PS.PhotoSyncError as e:
        raise HTTPException(502, str(e))
    D.audit(conn, uid, "foto_analizada",
            f"{len(result['rows'])} posiciones detectadas con {result['model']}")
    return result


@app.post("/api/hapi/photo/save")
def photo_save(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Guarda las filas confirmadas por el usuario tras revisar el análisis.
    Todo entra con fuente (modelo IA + fecha) y «pendiente de verificación»."""
    rows = body.get("rows") or []
    if not rows:
        raise HTTPException(400, "No hay filas para guardar")
    st = PS.config_status()
    model = st.get("model") or "modelo de visión"
    source = f"Hapi — captura analizada por IA ({model}, {D.now()[:10]}; pendiente de verificación)"
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
                         avg_cost=r.get("avg_cost"), invested=r.get("invested"),
                         hapi_value=r.get("hapi_value"), hapi_pl=r.get("hapi_pl"),
                         hapi_return_pct=r.get("hapi_return_pct"), source=source)
        position_upsert(pin, uid, conn)
        importadas.append(tk)
    cash = body.get("cash")
    try:
        cash = float(cash) if cash is not None else None
    except (TypeError, ValueError):
        cash = None
    if cash is not None and math.isfinite(cash):
        conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (?,?,?,?) "
                     "ON CONFLICT(user_id) DO UPDATE SET amount=excluded.amount, "
                     "currency=excluded.currency, updated_at=excluded.updated_at",
                     (uid, cash, "USD", D.now()))
    else:
        cash = None
    D.audit(conn, uid, "cartera_sincronizada_foto",
            f"{len(importadas)} importadas, {len(omitidas)} omitidas"
            + (f", efectivo {cash}" if cash is not None else "") + f" ({model})")
    return {"ok": True, "importadas": importadas, "omitidas": omitidas, "cash": cash,
            "detail": f"{len(importadas)} posición(es) sincronizada(s) desde la foto"
                      + (f" y efectivo actualizado a $ {cash:.2f}" if cash is not None else "")
                      + ", marcadas «pendiente de verificación». Confírmalas en la validación de datos."}


# ---------- consultas a Luna (sin modificar la cartera) ----------

@app.get("/api/assistant/status")
def assistant_status(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return PS.config_status()


@app.post("/api/assistant/ask")
def assistant_ask(body: AssistantQuestion, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Escribe una pregunta para Luna")
    positions = enrich_positions(conn, uid)
    risk = risk_get(uid, conn)
    context = AI.context_for_user(conn, uid, positions, risk)
    try:
        return AI.ask(question, context)
    except AI.AssistantError as e:
        raise HTTPException(502, str(e)) from e


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
    if not body.ticker.strip() or not body.source.strip():
        raise HTTPException(400, "Indica un ticker y la fuente del precio")
    if not math.isfinite(body.price) or body.price <= 0:
        raise HTTPException(400, "El precio debe ser un número positivo y finito")
    date_status = MD.staleness(body.asof)["status"]
    if date_status in ("sin_fecha", "fecha_futura"):
        raise HTTPException(400, "Indica una fecha válida que no esté en el futuro")
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, created_at) VALUES (?,?,?,?,?,?)",
                 (body.ticker.upper().strip(), body.price, body.currency, body.asof, body.source.strip(), D.now()))
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
            "staleness": MD.staleness(row["asof"]) if row else None,
            "period": row["period"] if row else None, "unit": row["unit"] if row else None,
            "shares_unit": row["shares_unit"] if row else None}


@app.put("/api/fundamentals/{ticker}")
def fundamentals_put(ticker: str, body: FundamentalsIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if not body.source.strip() or not body.asof.strip():
        raise HTTPException(400, "Fuente y fecha del dato son obligatorias")
    conn.execute("INSERT INTO fundamentals (user_id, ticker, data, source, asof, created_at) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT(user_id, ticker) DO UPDATE SET data=excluded.data, source=excluded.source, "
                 "asof=excluded.asof, created_at=excluded.created_at, "
                 "period=NULL, unit=NULL, shares_unit=NULL",
                 (uid, ticker.upper(), json.dumps(body.data, ensure_ascii=False), body.source, body.asof, D.now()))
    D.audit(conn, uid, "fundamentales_guardados", ticker)
    return {"ok": True}


# ---------- importaciones confirmadas por el usuario (Luna solo propone) ----------


def _photo_input(body):
    try:
        AP.image_input(body.get("image_b64"), body.get("mime"))
    except AP.AIProviderError as exc:
        raise HTTPException(400, str(exc)) from exc
    return body["image_b64"], body["mime"]


@app.post("/api/fundamentals/photo/analyze")
def fundamentals_photo_analyze(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    image, mime = _photo_input(body)
    try:
        return FS.analyze(image, mime)
    except FS.FundSyncError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/fundamentals/{ticker}/photo/save")
def fundamentals_photo_save(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk):
        raise HTTPException(400, "Ticker inválido")
    source = body.get("source")
    if not isinstance(source, str) or not source.strip() or len(source.strip()) > 500:
        raise HTTPException(400, "Confirma una fuente válida (máximo 500 caracteres)")
    asof = body.get("asof")
    if not isinstance(asof, str) or not FS.ISO_DATE.fullmatch(asof):
        raise HTTPException(400, "Confirma una fecha de cierre YYYY-MM-DD")
    try:
        if date.fromisoformat(asof) > datetime.now(timezone.utc).date():
            raise ValueError("fecha futura")
    except ValueError as exc:
        raise HTTPException(400, "Fecha de cierre inválida o futura") from exc
    if body.get("replace_existing", False) not in (True, False) or not isinstance(body.get("replace_existing", False), bool):
        raise HTTPException(400, "replace_existing debe ser booleano")
    try:
        data = FS.confirmed_data(body.get("data"), body.get("unit"),
                                 body.get("shares_unit"), body.get("period"))
    except FS.FundSyncError as exc:
        raise HTTPException(400, str(exc)) from exc
    existing = conn.execute("SELECT id FROM fundamentals WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
    if existing and body.get("replace_existing") is not True:
        raise HTTPException(400, "Ya hay fundamentales; confirma replace_existing:true para reemplazar el período completo")
    conn.execute("INSERT INTO fundamentals (user_id, ticker, data, source, asof, created_at, period, unit, shares_unit) "
                 "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id, ticker) DO UPDATE SET "
                 "data=excluded.data, source=excluded.source, asof=excluded.asof, "
                 "created_at=excluded.created_at, period=excluded.period, unit=excluded.unit, "
                 "shares_unit=excluded.shares_unit",
                 (uid, tk, json.dumps(data, ensure_ascii=False), source.strip(), asof, D.now(),
                  body["period"], body.get("unit"), body.get("shares_unit")))
    D.audit(conn, uid, "fundamentales_foto_confirmados", f"{tk} {body['period']} {asof}; {source.strip()}")
    return {"ok": True, "ticker": tk, "fundamentals": data, "source": source.strip(),
            "asof": asof, "period": body["period"], "unit": body.get("unit"),
            "shares_unit": body.get("shares_unit")}


@app.post("/api/trades/photo/analyze")
def trades_photo_analyze(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    image, mime = _photo_input(body)
    try:
        return TS.analyze(image, mime)
    except TS.TradeSyncError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/trades/import")
def trades_import(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = body.get("rows")
    source = body.get("source")
    if (body.get("reviewed") is not True or not isinstance(rows, list) or not rows
            or not isinstance(source, str) or not source.strip() or len(source.strip()) > 500):
        raise HTTPException(400, "Confirma filas revisadas y una fuente válida")
    if not isinstance(body.get("allow_duplicates", False), bool):
        raise HTTPException(400, "allow_duplicates debe ser booleano")
    confirmed_source = source.strip() + " — confirmado por usuario"
    model = body.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 120):
        raise HTTPException(400, "Modelo inválido")
    normalized, fingerprints = [], []
    for index, row in enumerate(rows):
        try:
            trade = TS.normalize_trade(row, require_complete=True)
            fingerprint = TS.trade_fingerprint(trade)
            if not all(math.isfinite(float(trade[key])) for key in ("qty", "price", "fees")):
                raise TS.TradeSyncError("Los números exceden la precisión de SQLite")
        except (TS.TradeSyncError, OverflowError) as exc:
            raise HTTPException(400, {"row": index, "error": str(exc)}) from exc
        normalized.append(trade)
        fingerprints.append(fingerprint)

    # Bloquea importaciones concurrentes entre el chequeo de duplicados y las escrituras.
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute("SELECT s.trade_id, s.fingerprint, s.order_id, t.ticker "
                            "FROM trade_sources s JOIN trades t ON t.id=s.trade_id "
                            "WHERE s.user_id=?", (uid,)).fetchall()
    known, order_ids = {}, {}
    for item in existing:
        known.setdefault(item["fingerprint"], []).append(item["trade_id"])
        if item["order_id"]:
            order_ids.setdefault((item["ticker"], item["order_id"]), []).append(item["trade_id"])
    duplicates = []
    for index, (trade, fingerprint) in enumerate(zip(normalized, fingerprints)):
        order_key = (trade["ticker"], trade.get("order_id"))
        matches = list(dict.fromkeys(known.get(fingerprint, []) + order_ids.get(order_key, [])))
        if matches:
            duplicates.append({"row": index, "fingerprint": fingerprint,
                               "matches": matches})
        known.setdefault(fingerprint, []).append(f"batch:{index}")
        if trade.get("order_id"):
            order_ids.setdefault(order_key, []).append(f"batch:{index}")
    if duplicates and body.get("allow_duplicates") is not True:
        raise HTTPException(400, {"message": "Posibles órdenes duplicadas; revisa y confirma allow_duplicates:true",
                                  "duplicates": duplicates})
    ids = []
    try:
        for trade, fingerprint in zip(normalized, fingerprints):
            cur = conn.execute("INSERT INTO trades (user_id, ticker, side, qty, price, fees, currency, at, created_at) "
                               "VALUES (?,?,?,?,?,?,?,?,?)",
                               (uid, trade["ticker"], trade["side"], float(trade["qty"]),
                                float(trade["price"]), float(trade["fees"]), "USD", trade["at"], D.now()))
            ids.append(cur.lastrowid)
            conn.execute("INSERT INTO trade_sources (trade_id, user_id, source, model, order_id, fingerprint, imported_at) "
                         "VALUES (?,?,?,?,?,?,?)",
                         (cur.lastrowid, uid, confirmed_source, model, trade.get("order_id"), fingerprint, D.now()))
        D.audit(conn, uid, "operaciones_importadas", f"{len(ids)} filas; fuente: {confirmed_source}; duplicados: {len(duplicates)}")
    except Exception:
        conn.rollback()
        raise
    return {"ok": True, "ids": ids, "imported": len(ids), "duplicates": duplicates,
            "warnings": ["Posibles duplicados importados con confirmación explícita"] if duplicates else []}


@app.get("/api/trades")
def trades_list(ticker: Optional[str] = None, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if ticker is not None and not TS.TICKER.fullmatch(ticker.strip().upper()):
        raise HTTPException(400, "Ticker inválido")
    rows = conn.execute("SELECT t.*, s.source, s.model, s.order_id, s.fingerprint, s.imported_at "
                        "FROM trades t LEFT JOIN trade_sources s ON s.trade_id=t.id AND s.user_id=t.user_id "
                        "WHERE t.user_id=? AND (? IS NULL OR t.ticker=?) ORDER BY t.at, t.id",
                        (uid, ticker.upper().strip() if ticker else None,
                         ticker.upper().strip() if ticker else None)).fetchall()
    return {"trades": [dict(row) for row in rows]}


RECONCILE_WARNING = ("Si hubo splits o transferencias, no apliques este costo: el libro solo modela compras y ventas. "
                     "SQLite almacena números de operaciones y posiciones como REAL; "
                     "puede haber diferencias de precisión flotante.")


def _ledger_snapshot(uid, ticker, position, trades):
    """Vincula la confirmación a las órdenes y al costo que el usuario vio."""
    payload = [uid, ticker, [position[key] for key in
                            ("qty", "avg_cost", "invested", "verified", "updated_at")],
               [[row[key] for key in ("id", "side", "qty", "price", "fees", "currency", "at",
                                      "source", "order_id", "fingerprint")] for row in trades]]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


@app.post("/api/trades/{ticker}/reconcile")
def trades_reconcile(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk) or body.get("complete_history") is not True:
        raise HTTPException(400, "Confirma ticker e historial completo, incluidos splits y transferencias")
    if not isinstance(body.get("apply", False), bool):
        raise HTTPException(400, "apply debe ser booleano")
    # Serializa la verificación de cantidad con la actualización para evitar replays obsoletos.
    if body.get("apply") is True:
        conn.execute("BEGIN IMMEDIATE")
    pos = conn.execute("SELECT * FROM positions WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
    if not pos or pos["verified"] != 1 or pos["currency"] != "USD" or not math.isfinite(pos["qty"]):
        raise HTTPException(400, "Se necesita una posición existente, verificada y en USD")
    trades = conn.execute("SELECT t.*, s.source, s.order_id, s.fingerprint FROM trades t "
                          "LEFT JOIN trade_sources s ON s.trade_id=t.id AND s.user_id=t.user_id "
                          "WHERE t.user_id=? AND t.ticker=? ORDER BY t.id", (uid, tk)).fetchall()
    if not trades or any(not r["source"] or not r["fingerprint"] or not r["at"] or
                         r["fees"] is None or r["currency"] != "USD" for r in trades):
        raise HTTPException(400, "Historial incompleto o con operaciones sin procedencia verificable")
    ledger = [{**dict(r), **({"order_id": r["order_id"]} if r["order_id"] else {})} for r in trades]
    try:
        basis = TS.cost_basis(ledger)
    except TS.TradeSyncError as exc:
        raise HTTPException(400, str(exc)) from exc
    position_qty = Decimal(str(pos["qty"]))
    tolerance = Decimal("0.00001")
    if abs(basis["qty"] - position_qty) > tolerance:
        raise HTTPException(400, "La cantidad del historial no coincide con la posición verificada")
    try:
        value = body.get("confirmed_qty")
        if isinstance(value, bool) or value is None:
            raise InvalidOperation
        confirmed = Decimal(str(value))
        if (not confirmed.is_finite() or confirmed <= 0 or
                abs(confirmed - position_qty) > tolerance or abs(confirmed - basis["qty"]) > tolerance):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(400, "confirmed_qty debe coincidir con el historial y la posición actual") from exc
    snapshot = _ledger_snapshot(uid, tk, pos, trades)
    if body.get("apply") is True:
        if body.get("no_unmodeled_adjustments") is not True:
            raise HTTPException(400, "No se puede aplicar costo con splits, transferencias u otros ajustes sin modelar")
        token = body.get("preview_token")
        if not isinstance(token, str) or not secrets.compare_digest(token, snapshot):
            raise HTTPException(400, "El libro o la posición cambiaron: vuelve a calcular la vista previa")
        if not all(math.isfinite(float(basis[key])) for key in ("avg_cost", "invested")):
            raise HTTPException(400, "El costo supera la precisión de SQLite")
        conn.execute("UPDATE positions SET avg_cost=?, invested=?, verified=0, updated_at=? "
                     "WHERE user_id=? AND ticker=?",
                     (float(basis["avg_cost"]), float(basis["invested"]), D.now(), uid, tk))
        D.audit(conn, uid, "costo_reconciliado", f"{tk} qty={basis['qty']} operaciones={len(trades)}")
    return {"qty": str(basis["qty"]), "invested": str(basis["invested"]),
            "avg_cost": str(basis["avg_cost"]), "position_qty": pos["qty"],
            "preview_token": snapshot if body.get("apply") is not True else None,
            "reconciled": True, "applied": body.get("apply") is True,
            "warning": RECONCILE_WARNING}


# ---------- Módulos 4-7 y 14: análisis y recomendación ----------

@app.post("/api/analysis/{ticker}")
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


@app.post("/api/decisions/{did}/explain")
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
        RV._required_text(report["decision_propuesta"], "decision_propuesta", 40)
        if report["decision_propuesta"] not in RV.ACTIONS:
            raise RV.ReviewError("Decisión inválida")
        for key in RV.REPORT_FIELDS:
            if key == "argumentos":
                RV._list(report[key], key, 10, 1000)
            elif key != "decision_propuesta":
                RV._text(report[key], key, 1000)
    except (ValueError, TypeError, RV.ReviewError) as exc:
        raise HTTPException(400, "Decisión guardada sin argumentos válidos para explicar") from exc
    try:
        return RV.explain(report)
    except RV.ReviewError as exc:
        raise HTTPException(502, str(exc)) from exc


# ---------- Módulo 8: riesgo ----------

@app.get("/api/risk")
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
    missing_value = without_current_value(positions)
    if missing_value:
        raise HTTPException(400, "Simulación no calculable: actualiza valores en USD de " + ", ".join(missing_value))
    cash_row = conn.execute("SELECT amount, currency FROM cash WHERE user_id=?", (uid,)).fetchone()
    if cash_unsupported(cash_row):
        raise HTTPException(400, "Simulación no calculable: el efectivo no está en USD")
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


@app.post("/api/journal/{jid}/challenge")
def journal_challenge(jid: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT data, ticker, created_at FROM journal WHERE id=? AND user_id=?", (jid, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Entrada no encontrada")
    try:
        entry = json.loads(row["data"])
        if not isinstance(entry, dict):
            raise ValueError("entrada inválida")
        entry = {**entry, "ticker": row["ticker"], "created_at": row["created_at"]}
        RV._required_text(entry.get("tesis"), "tesis", 3000)
        for key in RV.ENTRY_FIELDS:
            if key == "fuentes":
                if isinstance(entry.get(key), list):
                    RV._list(entry[key], key, 10, 500)
                else:
                    RV._text(entry.get(key), key, 1000)
            elif key != "tesis":
                RV._text(entry.get(key), key, 1000)
    except (ValueError, TypeError, RV.ReviewError) as exc:
        raise HTTPException(400, "Entrada de diario inválida para revisión") from exc
    try:
        return RV.challenge(entry)
    except RV.ReviewError as exc:
        raise HTTPException(502, str(exc)) from exc


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
    return {"portfolio": pf, "risk": {k: rk.get(k) for k in ("error", "hhi", "nivel_concentracion",
                                                             "diversificacion_efectiva", "sectores",
                                                             "correlacion", "incumplimientos")},
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
    for t in ("positions", "trade_sources", "trades", "fundamentals", "journal", "decisions", "candidates",
              "alerts", "settings", "audit_log", "cash"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados"}


@app.get("/")
def index():
    # no-cache: la página es un solo archivo que cambia con el código; sin esta
    # cabecera el navegador mostraba una versión vieja y faltaban funciones nuevas.
    return FileResponse(os.path.join(STATIC_DIR, "index.html"),
                        headers={"Cache-Control": "no-cache"})
