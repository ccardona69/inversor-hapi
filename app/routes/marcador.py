"""Fase 1: marcador de bolsillo, fantasma SPY, alcancía y los tres avisos.

El marcador compara lo que salió del bolsillo (depósitos netos + costos de
depósito) con lo que vale la cartera hoy; el fantasma muestra el mismo dinero
invertido en el índice a retorno total. Las descargas de Yahoo (SPY y PEN=X)
se cachean 6 h; si Yahoo falla, el fantasma queda «sin dato» y los costos se
estiman con la tarifa configurada — jamás con el tc implícito ni fx_default.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from .. import alcancia as AL
from .. import db as D
from .. import flowsync as FS
from .. import marketdata as MD
from .. import scoreboard as SB
from ..deps import _photo_input, conn_dep, current_user
from .portfolio import portfolio

router = APIRouter()

CACHE_TTL_S = 6 * 3600
_cache = {}


def _clear_cache():
    _cache.clear()


def _history(ticker):
    """Histórico 5y con caché de 6 h. Lanza MarketDataError si Yahoo falla."""
    hit = _cache.get(ticker)
    now = datetime.now(timezone.utc)
    if hit and (now - hit[0]).total_seconds() < CACHE_TTL_S:
        return hit[1]
    data = MD.fetch_history(ticker, "5y")
    _cache[ticker] = (now, data)
    return data


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def estado_plan(conn, uid):
    """Foto del plan: ajustes con defaults, movimientos y valor de la cartera.

    Los defaults viven en SETTINGS_DEFAULTS: nunca se escriben a la BD por
    leerlos. `valor_actual` incluye el efectivo solo si está en USD."""
    settings = {k: D.get_setting(conn, uid, k, v) for k, v in SB.SETTINGS_DEFAULTS.items()}
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM contributions WHERE user_id=? ORDER BY at, id", (uid,))]
    pf = portfolio(uid, conn)
    # Solo posiciones verificadas alimentan el marcador: una captura analizada
    # por IA «pendiente de verificación» no puede entrar a una línea HECHO.
    ver = [p for p in pf["positions"] if p["verified"]]
    sin_verificar = sorted({p["ticker"] for p in pf["positions"] if not p["verified"]})
    missing = [p["ticker"] for p in ver if p["market_value"] is None]
    cash_row = conn.execute("SELECT updated_at FROM cash WHERE user_id=?", (uid,)).fetchone()
    if missing or pf["cash"] is None or (not ver and cash_row is None):
        valor = None  # precio faltante, efectivo en otra moneda o cartera no registrada
    else:
        valor = round(sum(p["market_value"] for p in ver) + (pf.get("cash") or 0), 2)
    # Pesos y etf_pct miden exposición (todas las posiciones con precio),
    # no solo lo verificado: si lo sin verificar es una acción, excluirla
    # inflaría etf_pct y el guard de Luna quedaría fail-open.
    exposicion = [p for p in pf["positions"] if p["market_value"] is not None]
    total_exp = sum(p["market_value"] for p in exposicion)
    pesos = {p["ticker"]: round(p["market_value"] / total_exp * 100, 2)
             for p in exposicion} if total_exp else {}
    etf_pct = SB.etf_pct(exposicion)
    asofs = [p["price_info"]["asof"] for p in ver
             if (p.get("price_info") or {}).get("asof")]
    return {"settings": settings, "rows": rows, "valor_actual": valor,
            "valor_asof": (min(asofs) if asofs else cash_row["updated_at"] if cash_row else None)
                          if valor is not None else None,
            "valor_fuente": ("precios registrados en Cartera" if ver else
                             "efectivo registrado en Cartera") if valor is not None else None,
            "efectivo_pendiente": bool(ver and cash_row is None),
            "sin_verificar": sin_verificar,
            "pesos": pesos, "etf_pct": etf_pct, "etf_target_pct": settings["etf_target_pct"]}


def _fx_lookup(fx_rows):
    """tc de mercado del día del depósito (o del día hábil anterior), ya
    normalizado a soles por dólar. None si Yahoo no dio un valor usable."""
    series = sorted((r for r in (fx_rows or []) if r.get("close") is not None),
                    key=lambda r: r["date"])

    def lookup(date_str):
        cand = None
        for r in series:
            if r["date"] <= date_str:
                cand = r
            else:
                break
        if cand is None:
            return None
        tc = SB.normalize_tc(cand["close"])
        return (tc, "Yahoo Finance PEN=X", cand["date"]) if tc is not None else None

    return lookup


def _avisos(settings, alc):
    """Solo tres avisos del plan: meta de alcancía, inactividad en Hapi y W-8BEN."""
    hoy = date.today()
    avisos = []
    if alc.get("llego_meta") and alc.get("meta_usd"):
        avisos.append({"type": "alcancia_meta",
                       "text": f"Tu alcancía llegó a la meta: toca depositar ~$ {round(alc['meta_usd'])}."})
    check = _parse_date(settings.get("last_hapi_check"))
    if check:
        dias = (hoy - check).days
        if dias >= 50:
            avisos.append({"type": "hapi_inactividad",
                           "text": f"Llevas {dias} días sin entrar a Hapi: entra un minuto para evitar la tarifa."})
    expiry = _parse_date(settings.get("w8ben_expiry"))
    if expiry:
        dias = (expiry - hoy).days
        if 0 <= dias <= 30:
            avisos.append({"type": "w8ben",
                           "text": f"Tu W-8BEN vence en {dias} días: renuévalo en la app de Hapi; "
                                   "sin él vigente pueden retenerte hasta ~24 % adicional."})
        elif dias < 0:
            avisos.append({"type": "w8ben",
                           "text": f"Tu W-8BEN venció hace {-dias} días: renuévalo en la app de Hapi; "
                                   "sin él vigente pueden retenerte hasta ~24 % adicional."})
    return avisos


@router.get("/api/marcador")
def marcador(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    estado = estado_plan(conn, uid)
    settings = estado["settings"]
    spy_rows, fx_rows = None, None
    fuente_spy = fuente_fx = None
    try:
        hist = _history("SPY")
        spy_rows, fuente_spy = hist["rows"], hist["source"]
    except MD.MarketDataError:
        pass  # fantasma «sin dato», el marcador sigue
    try:
        hist = _history("PEN=X")
        fx_rows, fuente_fx = hist["rows"], hist["source"]
    except MD.MarketDataError:
        pass  # costos de depósito quedan ESTIMACIÓN
    fee = float(settings["deposit_fee"] or 0)
    m = SB.marcador(estado["rows"], estado["valor_actual"], fee,
                    tc_lookup=_fx_lookup(fx_rows) if fx_rows else None)
    fantasma = SB.fantasma_spy(estado["rows"], spy_rows) if spy_rows else None
    if fantasma:
        fantasma["fuente"] = fuente_spy
        # Ambos parten del mismo depositado_neto: sin asimetría de costos.
        fantasma["diferencia"] = (round(estado["valor_actual"] - fantasma["valor_fantasma"], 2)
                                  if estado["valor_actual"] is not None else None)
    alc = AL.plan(estado["rows"], r=float(settings["r"] or 0), fee=fee,
                  fx=float(settings["fx_default"] or 0),
                  declarado_mensual=float(settings["ahorro_mensual_declarado"] or 0),
                  today=date.today())
    return {"marcador": m, "fantasma": fantasma, "alcancia": alc,
            "avisos": _avisos(settings, alc),
            "pesos": estado["pesos"], "etf_pct": estado["etf_pct"],
            "etf_target_pct": estado["etf_target_pct"],
            "fuentes": {"valor_actual": {"fuente": estado["valor_fuente"],
                                        "fecha": estado["valor_asof"],
                                        "efectivo_pendiente": estado["efectivo_pendiente"],
                                        "sin_verificar": estado["sin_verificar"]},
                        "spy": {"fuente": fuente_spy,
                                "fecha": fantasma["fecha_precio"] if fantasma else None},
                        "fx": {"fuente": fuente_fx}}}


@router.get("/api/alcancia")
def alcancia_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Solo la alcancía (§13): mismo cálculo que /api/marcador, sin red."""
    estado = estado_plan(conn, uid)
    s = estado["settings"]
    return AL.plan(estado["rows"], r=float(s["r"] or 0), fee=float(s["deposit_fee"] or 0),
                   fx=float(s["fx_default"] or 0),
                   declarado_mensual=float(s["ahorro_mensual_declarado"] or 0),
                   today=date.today())


# ---------- borrador → confirmación de movimientos (flows) ----------


def _draft_rows(result, conn, uid):
    known = {r["fingerprint"] for r in conn.execute(
        "SELECT fingerprint FROM contributions WHERE user_id=?", (uid,))}
    rows = []
    for row in result["rows"]:
        row = dict(row)
        if row.get("kind") in FS.CONTRIB_KINDS:
            row["fingerprint"] = FS.fingerprint(row)
            row["posible_duplicado"] = row["fingerprint"] in known
        rows.append(row)
    return {"rows": rows, "omitted": result.get("omitted", []),
            "model": result.get("model")}


@router.post("/api/flows/draft")
def flows_draft(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Entiende el mensaje o la captura y devuelve filas para revisar.
    Nada se guarda aquí: la confirmación vive en /api/flows/confirm."""
    if body.get("image_b64") is not None:
        image, mime = _photo_input(body)
        try:
            result = FS.analyze_image(image, mime)
        except FS.FlowSyncError as exc:
            raise HTTPException(502, str(exc)) from exc
    else:
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(400, "Escribe el mensaje o sube una captura")
        text = text.strip()
        parsed = FS.parse_message(text, date.today().isoformat())
        if parsed:
            result = {"rows": parsed, "omitted": [], "model": None}
        elif len(text) >= 40 or "\n" in text:
            try:
                result = FS.analyze_text(text)
            except FS.FlowSyncError as exc:
                raise HTTPException(502, str(exc)) from exc
        else:
            raise HTTPException(400, {
                "message": "No entendí el mensaje. Cuéntalo en una frase o pega tu historial de Hapi.",
                "ejemplos": ["guardé 80 soles",
                             "deposité 480 soles y llegaron 132.50",
                             "entré a Hapi",
                             "mi W-8BEN vence el 2027-03-01"]})
    return _draft_rows(result, conn, uid)


@router.post("/api/flows/confirm")
def flows_confirm(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Guarda movimientos ya revisados; detecta duplicados por fingerprint pero
    permite confirmarlos con allow_duplicates:true."""
    rows = body.get("rows")
    if body.get("reviewed") is not True or not isinstance(rows, list) or not rows:
        raise HTTPException(400, "Confirma las filas revisadas")
    if not isinstance(body.get("allow_duplicates", False), bool):
        raise HTTPException(400, "allow_duplicates debe ser booleano")
    normalized = []
    for index, raw in enumerate(rows):
        try:
            normalized.append(FS.normalize_row(raw))
        except FS.FlowSyncError as exc:
            raise HTTPException(400, {"row": index, "error": str(exc)}) from exc

    # Bloquea confirmaciones concurrentes entre el chequeo y las escrituras.
    conn.execute("BEGIN IMMEDIATE")
    known = {r["fingerprint"] for r in conn.execute(
        "SELECT fingerprint FROM contributions WHERE user_id=?", (uid,))}
    duplicates = []
    for index, row in enumerate(normalized):
        fp = row.get("fingerprint")
        if not fp:
            continue
        if fp in known:
            duplicates.append({"row": index, "fingerprint": fp})
        known.add(fp)
    if duplicates and body.get("allow_duplicates") is not True:
        raise HTTPException(400, {"message": "Posibles movimientos duplicados; revisa y confirma "
                                             "allow_duplicates:true",
                                  "duplicates": duplicates})
    ids, settings_updated = [], set()
    try:
        captura = False
        for row in normalized:
            if row["kind"] == "actividad":
                D.set_setting(conn, uid, "last_hapi_check", row["at"])
                settings_updated.add("last_hapi_check")
                continue
            if row["kind"] == "w8ben":
                D.set_setting(conn, uid, "w8ben_expiry", row["at"])
                settings_updated.add("w8ben_expiry")
                continue
            cur = conn.execute(
                "INSERT INTO contributions (user_id, kind, amount_usd, soles_amount, fx_rate, "
                "at, source, fingerprint, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, row["kind"], row["amount_usd"], row["soles_amount"], row["fx_rate"],
                 row["at"], row["source"], row["fingerprint"], D.now()))
            ids.append(cur.lastrowid)
            captura = captura or row["source"] == "captura"
        if captura:
            # Para tomar la captura el usuario estaba dentro de Hapi (proxy).
            hoy = date.today().isoformat()
            if (D.get_setting(conn, uid, "last_hapi_check") or "") < hoy:
                D.set_setting(conn, uid, "last_hapi_check", hoy)
                settings_updated.add("last_hapi_check")
    except Exception:
        conn.rollback()
        raise
    return {"ok": True, "imported": len(ids), "ids": ids,
            "settings_updated": sorted(settings_updated), "duplicates": duplicates}


@router.get("/api/flows")
def flows_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM contributions WHERE user_id=? ORDER BY at DESC, id DESC",
                        (uid,)).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.delete("/api/flows/{flow_id}")
def flows_delete(flow_id: int, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Quita un movimiento registrado por error."""
    cur = conn.execute("DELETE FROM contributions WHERE id=? AND user_id=?", (flow_id, uid))
    if not cur.rowcount:
        raise HTTPException(404, "Movimiento no encontrado")
    return {"ok": True}
