"""Radar de oportunidades: puntúa el universo fijo + watchlist + cartera con
precio (Yahoo) y fundamentales del 10-K (SEC).

El GET solo lee lo ya guardado (nunca toca la red); los POST son quienes
descargan precios y 10-K. Quitar un ticker de la watchlist se hace con el
DELETE /api/candidates/{id} ya existente.
"""
import json

from fastapi import APIRouter, Depends, HTTPException

from .. import db as D
from .. import marketdata as MD
from .. import radar as RADAR
from .. import risk as RK
from .. import secdata as SEC
from .. import tradesync as TS
from ..deps import conn_dep, current_user
from .market import _sec_fundamentals, store_quote
from .portfolio import position_rows

router = APIRouter()


def _radar_tickers(conn, uid):
    """Universo ∪ watchlist (candidates) ∪ posiciones, una entrada por ticker."""
    cand_by_tk = {}
    for r in conn.execute("SELECT * FROM candidates WHERE user_id=?", (uid,)).fetchall():
        tk = r["ticker"].upper()
        # candidates no tiene UNIQUE(user_id, ticker): si hay duplicados manuales
        # se muestra una sola fila con el id de la más reciente.
        if tk not in cand_by_tk or r["id"] > cand_by_tk[tk]["id"]:
            cand_by_tk[tk] = dict(r)
    pos_by_tk = {p["ticker"].upper(): p for p in position_rows(conn, uid)}
    tickers = set(RADAR.UNIVERSE) | set(cand_by_tk) | set(pos_by_tk)
    return tickers, cand_by_tk, pos_by_tk


@router.get("/api/radar")
def radar_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Solo datos guardados: nunca llama a Yahoo ni a la SEC."""
    tickers, cand_by_tk, pos_by_tk = _radar_tickers(conn, uid)
    items = []
    for tk in sorted(tickers):
        cand = cand_by_tk.get(tk)
        pos = pos_by_tk.get(tk)
        sector = ((pos or {}).get("sector") or RADAR.UNIVERSE.get(tk)
                  or RK.KNOWN_SECTORS.get(tk) or "sin clasificar")
        prow = D.latest_price(conn, tk)
        price = {"price": prow["price"], "currency": prow["currency"],
                 "asof": prow["asof"], "source": prow["source"],
                 "status": MD.staleness(prow["asof"])["status"]} if prow else None
        frow = conn.execute("SELECT data, source, asof FROM fundamentals "
                            "WHERE user_id=? AND ticker=?", (uid, tk)).fetchone()
        fdata = json.loads(frow["data"]) if frow else {}
        fund = {"data": fdata, "source": frow["source"], "asof": frow["asof"]} if frow else None
        s = RADAR.screen(tk, sector, (prow or {}).get("price"), fdata)
        items.append({**s,
                      "en_universo": tk in RADAR.UNIVERSE,
                      "en_watchlist": cand is not None,
                      "en_cartera": pos is not None,
                      "candidate_id": cand["id"] if cand else None,
                      "price": price, "fund": fund})
    order = {v: i for i, v in enumerate(RADAR.VERDICT_ORDER)}
    items.sort(key=lambda it: (order[it["veredicto"]], it["calidad"] is None,
                               -(it["calidad"] or 0), it["ticker"]))
    return {"items": items, "universo": len(RADAR.UNIVERSE),
            "nota": "Universo fijo de empresas grandes y líquidas de EE.UU.; "
                    "no es toda la bolsa ni una recomendación."}


def _refresh_one(tk, conn, uid):
    """Precio de Yahoo + 10-K de la SEC solo si faltan fundamentales.
    Los errores se devuelven, nunca abortan el resto del radar."""
    errores, precio, nuevo_fund = [], False, False
    try:
        store_quote(conn, {**MD.fetch_quote(tk), "ticker": tk})
        precio = True
    except MD.MarketDataError as e:
        errores.append({"ticker": tk, "error": str(e)})
    if not conn.execute("SELECT 1 FROM fundamentals WHERE user_id=? AND ticker=?",
                        (uid, tk)).fetchone():
        try:
            _sec_fundamentals(tk, conn, uid)
            nuevo_fund = True
        except SEC.SecDataError as e:
            errores.append({"ticker": tk, "error": e.detail})
    return precio, nuevo_fund, errores


@router.post("/api/radar/refresh")
def radar_refresh(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    tickers, _, _ = _radar_tickers(conn, uid)
    precios, nuevos, errores = 0, 0, []
    for tk in sorted(tickers):
        p, f, errs = _refresh_one(tk, conn, uid)
        precios += p
        nuevos += f
        errores += errs
    return {"ok": True, "precios": precios, "fundamentales_nuevos": nuevos,
            "errores": errores}


@router.post("/api/radar/{ticker}")
def radar_add(ticker: str, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """El usuario solo escribe el ticker: se agrega a su watchlist (candidates)
    y el sistema descarga su precio y sus fundamentales del 10-K."""
    tk = ticker.strip().upper()
    if not TS.TICKER.fullmatch(tk):
        raise HTTPException(400, "Ticker inválido")
    if not conn.execute("SELECT 1 FROM candidates WHERE user_id=? AND ticker=?",
                        (uid, tk)).fetchone():
        conn.execute("INSERT INTO candidates (user_id, ticker, name, data, source, created_at) "
                     "VALUES (?,?,?,?,?,?)", (uid, tk, "", "{}", "radar", D.now()))
    _, _, errores = _refresh_one(tk, conn, uid)
    return {"ok": True, "ticker": tk, "errores": errores}
