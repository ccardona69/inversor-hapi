"""Operaciones (trades): extracción por foto, importación con procedencia y
reconciliación del costo promedio contra el libro de órdenes."""
import hashlib
import json
import math
import secrets
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import db as D
from .. import tradesync as TS
from ..deps import _photo_input, conn_dep, current_user

router = APIRouter()


@router.post("/api/trades/photo/analyze")
def trades_photo_analyze(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    image, mime = _photo_input(body)
    try:
        return TS.analyze(image, mime)
    except TS.TradeSyncError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/api/trades/import")
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


@router.get("/api/trades")
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


@router.post("/api/trades/{ticker}/reconcile")
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
