"""Módulo 1: cartera — posiciones, efectivo y sincronización por foto.

La IA de visión propone filas; el usuario siempre revisa y confirma antes de
guardar, y todo entra marcado «pendiente de verificación» salvo que el usuario
marque que revisó cada dato.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import ai_provider as AP
from .. import db as D
from .. import marketdata as MD
from .. import photosync as PS
from .. import risk as RK
from ..deps import DISCLAIMER, conn_dep, current_user

router = APIRouter()


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
                    "day_change_pct": price.get("day_change_pct") if price and st["usable_as_current"] else None,
                    "return_pct": round(pl / p["invested"] * 100, 2) if pl is not None and p["invested"] else None,
                    "price_info": basis, "price_status": st["status"]})
    return out


def without_current_value(positions):
    return [p["ticker"] for p in positions
            if p["market_value"] is None or p["price_status"] not in ("actual", "reciente")
            or (p["currency"] or "USD").upper() != "USD"]


def cash_unsupported(cash_row):
    return bool(cash_row and (cash_row["currency"] or "USD").upper() != "USD")


@router.get("/api/portfolio")
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
    if positions and not missing_value and all(p["day_change_pct"] is not None for p in positions):
        prev = sum(p["market_value"] / (1 + p["day_change_pct"] / 100) for p in positions)
        cambio_dia = round(total_mv - prev, 2)
        cambio_dia_pct = round((total_mv / prev - 1) * 100, 2) if prev else None
    else:
        cambio_dia = cambio_dia_pct = None
    return {
        "positions": positions, "cash": cash,
        "cash_currency": cash_row["currency"] if cash_row else "USD",
        "totals": {"invertido": round(invested, 2) if not missing_cost else None,
                   "valor_actual": round(total_mv, 2) if not missing_value else None,
                   "resultado": round(total_mv - invested, 2) if complete and invested else None,
                   "rendimiento_pct": round((total_mv / invested - 1) * 100, 2) if complete and invested else None,
                   "cambio_dia": cambio_dia, "cambio_dia_pct": cambio_dia_pct,
                   "pesos_pct": weights, "sin_precio_vigente": missing_value, "sin_costo": missing_cost},
        "disclaimer": DISCLAIMER,
    }


@router.post("/api/positions")
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
    return {"ok": True}


@router.delete("/api/positions/{ticker}")
def position_delete(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("DELETE FROM positions WHERE user_id=? AND ticker=?", (uid, ticker.upper()))
    return {"ok": True}


@router.put("/api/cash")
def cash_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if (body.get("currency") or "USD").upper() != "USD":
        raise HTTPException(400, "Solo se admite efectivo en USD; no hay tipo de cambio verificado")
    try:
        amount = float(body.get("amount") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "El efectivo debe ser un número finito")
    if not math.isfinite(amount):
        raise HTTPException(400, "El efectivo debe ser un número finito")
    D.cash_upsert(conn, uid, amount)
    return {"ok": True}


def _upsert_rows(rows, uid, conn, source, capture_fields=False):
    """Guarda filas ya revisadas (de la foto): valida ticker/cantidad, hace el
    upsert y reporta qué filas se omitieron y por qué."""
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
        capture = {"hapi_value": r.get("hapi_value"), "hapi_pl": r.get("hapi_pl"),
                   "hapi_return_pct": r.get("hapi_return_pct")} if capture_fields else {}
        pin = PositionIn(ticker=tk, name=str(r.get("name") or ""), qty=qty,
                         avg_cost=r.get("avg_cost"), invested=r.get("invested"),
                         source=source, **capture)
        position_upsert(pin, uid, conn)
        importadas.append(tk)
    return importadas, omitidas


# ---------- sincronización con Hapi por foto (IA de visión) ----------

@router.get("/api/hapi/photo/status")
@router.get("/api/assistant/status")
def photo_status(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return AP.config_status()


@router.post("/api/hapi/photo/analyze")
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
    return result


@router.post("/api/hapi/photo/save")
def photo_save(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Guarda las filas que el usuario revisó tras el análisis de la captura.

    confirmed=True marca las filas importadas como verificadas; replace_all=True
    borra además las posiciones que no aparecen en la captura. Reemplazar exige
    confirmación y al menos una fila válida, y nada se escribe si falta alguna."""
    rows = body.get("rows") or []
    if not rows:
        raise HTTPException(400, "No hay filas para guardar")
    confirmed = bool(body.get("confirmed"))
    replace_all = bool(body.get("replace_all"))
    if replace_all and not confirmed:
        raise HTTPException(400, "Para reemplazar tu cartera, primero confirma que revisaste cada dato.")
    if replace_all:
        valid = []
        for r in rows:
            tk = str(r.get("ticker") or "").upper().strip()
            try:
                qty = float(r.get("qty"))
            except (TypeError, ValueError):
                qty = 0.0
            if tk and qty > 0:
                valid.append(tk)
        if not valid:
            raise HTTPException(400, "La captura no tiene filas válidas; no se puede reemplazar la cartera.")
    st = AP.config_status()
    model = st.get("model") or "modelo de visión"
    source = f"Hapi — captura analizada por IA ({model}, {D.now()[:10]}; pendiente de verificación)"
    importadas, omitidas = _upsert_rows(rows, uid, conn, source, capture_fields=True)
    if confirmed and importadas:
        marks = ",".join("?" * len(importadas))
        conn.execute(f"UPDATE positions SET verified=1, updated_at=? WHERE user_id=? AND ticker IN ({marks})",
                     (D.now(), uid, *importadas))
    eliminadas = []
    if replace_all:
        keep = set(importadas)
        eliminadas = sorted(p["ticker"] for p in position_rows(conn, uid) if p["ticker"] not in keep)
        for tk in eliminadas:
            conn.execute("DELETE FROM positions WHERE user_id=? AND ticker=?", (uid, tk))
    cash = body.get("cash")
    try:
        cash = float(cash) if cash is not None else None
    except (TypeError, ValueError):
        cash = None
    if cash is not None and math.isfinite(cash):
        D.cash_upsert(conn, uid, cash)
    else:
        cash = None
    detail = f"{len(importadas)} posición(es) sincronizada(s) desde la foto" \
        + (" y confirmadas" if confirmed else ", marcadas «pendiente de verificación»") \
        + (f" y efectivo actualizado a $ {cash:.2f}" if cash is not None else "") \
        + (f"; se quitaron {len(eliminadas)} que no aparecían en la captura" if eliminadas else "") \
        + ("." if confirmed else ". Confírmalas en la validación de datos.")
    return {"ok": True, "importadas": importadas, "omitidas": omitidas,
            "eliminadas": eliminadas, "cash": cash, "detail": detail}


@router.post("/api/positions/verify_all")
def verify_all(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    cur = conn.execute("UPDATE positions SET verified=1, updated_at=? WHERE user_id=? AND verified=0",
                       (D.now(), uid))
    return {"ok": True, "confirmadas": cur.rowcount}


# ---------- Módulo 2: validación ----------

@router.get("/api/validate")
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


@router.post("/api/positions/{ticker}/verify")
def verify_position(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    conn.execute("UPDATE positions SET verified=1, updated_at=? WHERE user_id=? AND ticker=?",
                 (D.now(), uid, ticker.upper()))
    return {"ok": True}
