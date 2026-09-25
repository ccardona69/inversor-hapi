"""Módulo 3: precios de mercado con fuente y fecha, y fundamentales manuales o por foto."""
import json
import math
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import analysis as AN
from .. import db as D
from .. import fundsync as FS
from .. import marketdata as MD
from .. import marketpulse as MP
from .. import secdata as SEC
from .. import tradesync as TS
from ..deps import _photo_input, conn_dep, current_user
from .portfolio import position_rows

router = APIRouter()


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


def store_quote(conn, q):
    conn.execute("INSERT INTO prices (ticker, price, currency, asof, source, day_change_pct, created_at) VALUES (?,?,?,?,?,?,?)",
                 (q["ticker"], q["price"], q["currency"], q["asof"], q["source"], q["day_change_pct"], D.now()))


@router.post("/api/prices/refresh")
def prices_refresh(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    results, errors = [], []
    tickers = {p["ticker"] for p in position_rows(conn, uid)}
    tickers |= {r["ticker"] for r in conn.execute("SELECT ticker FROM candidates WHERE user_id=?", (uid,)).fetchall()}
    for tk in sorted(tickers):
        try:
            q = MD.fetch_quote(tk)
            store_quote(conn, {**q, "ticker": tk})
            results.append(q)
        except MD.MarketDataError as e:
            errors.append({"ticker": tk, "error": str(e)})
    return {"updated": results, "errors": errors}


@router.post("/api/prices/manual")
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
    return {"ok": True}


# ---------- pulso de mercado y niveles por acción (regla técnica, no predicción) ----------

def _clear_cache():
    MP._clear_cache()


@router.get("/api/market/pulse")
def market_pulse(uid: int = Depends(current_user)):
    return MP.cached_pulse()


@router.get("/api/levels/{ticker}")
def levels_get(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tk = ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk):
        raise HTTPException(400, "Ticker inválido")
    try:
        base, fresh = MP.cached_levels(tk)
    except MD.MarketDataError as e:
        raise HTTPException(400, f"No se pudo obtener el precio de {tk}: {e}") from e
    if fresh:
        store_quote(conn, {**base["quote"], "ticker": tk})
    pos = next((p for p in position_rows(conn, uid) if p["ticker"] == tk), None)
    posicion = (MP.posicion_vs_niveles(base["precio"]["valor"], base["niveles"], pos.get("avg_cost"), pos.get("qty"))
                if pos else None)
    return {k: base[k] for k in ("ticker", "precio", "tecnica", "niveles", "fetched_at")} | {"posicion": posicion}


# ---------- fundamentales ----------

@router.get("/api/fundamentals/{ticker}")
def fundamentals_get(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT * FROM fundamentals WHERE user_id=? AND ticker=?", (uid, ticker.upper())).fetchone()
    return {"ticker": ticker.upper(),
            "fields": AN.FUND_FIELDS,
            "fundamentals": json.loads(row["data"]) if row else {},
            "source": row["source"] if row else None, "asof": row["asof"] if row else None,
            "staleness": MD.staleness(row["asof"]) if row else None,
            "period": row["period"] if row else None, "unit": row["unit"] if row else None,
            "shares_unit": row["shares_unit"] if row else None}


@router.put("/api/fundamentals/{ticker}")
def fundamentals_put(ticker: str, body: FundamentalsIn, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if not body.source.strip() or not body.asof.strip():
        raise HTTPException(400, "Fuente y fecha del dato son obligatorias")
    conn.execute("INSERT INTO fundamentals (user_id, ticker, data, source, asof, created_at) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT(user_id, ticker) DO UPDATE SET data=excluded.data, source=excluded.source, "
                 "asof=excluded.asof, created_at=excluded.created_at, "
                 "period=NULL, unit=NULL, shares_unit=NULL",
                 (uid, ticker.upper(), json.dumps(body.data, ensure_ascii=False), body.source, body.asof, D.now()))
    return {"ok": True}


# ---------- importaciones confirmadas por el usuario (Luna solo propone) ----------

@router.post("/api/fundamentals/photo/analyze")
def fundamentals_photo_analyze(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    image, mime = _photo_input(body)
    try:
        return FS.analyze(image, mime)
    except FS.FundSyncError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/api/fundamentals/{ticker}/photo/save")
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
    return {"ok": True, "ticker": tk, "fundamentals": data, "source": source.strip(),
            "asof": asof, "period": body["period"], "unit": body.get("unit"),
            "shares_unit": body.get("shares_unit")}


def _sec_fundamentals(tk, conn, uid):
    """Descarga y guarda los fundamentales del último 10-K. Solo la llama quien
    ya comprobó que no hay fundamentales o que el usuario autorizó reemplazarlos."""
    result = SEC.fetch_fundamentals(tk)
    source = (f"SEC EDGAR — 10-K del ejercicio cerrado el {result['period_end']} "
              f"(presentado {result['filed']}, accn {result['accn']}); "
              "márgenes y crecimientos calculados con el mismo 10-K")
    conn.execute("INSERT INTO fundamentals (user_id, ticker, data, source, asof, created_at, period, unit, shares_unit) "
                 "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id, ticker) DO UPDATE SET "
                 "data=excluded.data, source=excluded.source, asof=excluded.asof, "
                 "created_at=excluded.created_at, period=excluded.period, unit=excluded.unit, "
                 "shares_unit=excluded.shares_unit",
                 (uid, tk, json.dumps(result["data"], ensure_ascii=False), source,
                  result["period_end"], D.now(), "anual", "USD", "acciones"))
    return {**result, "source": source}


@router.post("/api/fundamentals/{ticker}/sec")
def fundamentals_sec(ticker: str, body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Carga los fundamentales del 10-K más reciente publicado en la SEC."""
    tk = ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk):
        raise HTTPException(400, "Ticker inválido")
    existing = conn.execute("SELECT source FROM fundamentals WHERE user_id=? AND ticker=?",
                            (uid, tk)).fetchone()
    if existing and body.get("replace_existing") is not True:
        raise HTTPException(409, f"Ya hay fundamentales para {tk} (fuente: {existing['source']}). "
                                 "Confirma para reemplazarlos por los del 10-K.")
    try:
        result = _sec_fundamentals(tk, conn, uid)
    except SEC.SecDataError as exc:
        raise HTTPException(exc.status, exc.detail) from exc
    return {"ok": True, "ticker": tk, "fundamentals": result["data"], "source": result["source"],
            "asof": result["period_end"], "missing": result["missing"], "detalle": result["detalle"]}
