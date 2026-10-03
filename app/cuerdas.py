"""Cuerdas de Ulises: límites y perfil de riesgo con enfriamiento.

Aflojar un límite es justamente lo que haría Ulises sin las cuerdas: por eso
todo cambio que afloja espera ENFRIAMIENTO_DIAS días con motivo registrado en
el Diario. Endurecer o igualar aplica de inmediato y retira esa clave del
lote pendiente. Una nueva petición que afloja reemplaza el lote completo y
reinicia el reloj. Sin esquema nuevo: todo vive en `settings` como clave/valor
(`limits_pendientes`, `risk_profile_pendientes`) más filas de `journal`.
"""
import json
import math
from datetime import datetime, timedelta, timezone

from . import db as D
from . import risk as RK

ENFRIAMIENTO_DIAS = 7

_NIVELES_RIESGO = {"conservador": 0, "moderado": 1, "agresivo": 2}

# clave → (tipo, mínimo, máximo, dirección que afloja)
LIMIT_RULES = {
    "max_position_pct": ("num", 0, 100, "up"),
    "max_sector_pct": ("num", 0, 100, "up"),
    "max_trade_pct": ("num", 0, 100, "up"),
    "max_tolerable_loss_pct": ("num", 0, 100, "up"),
    "max_trades_per_month": ("int", 0, 100, "up"),
    "min_cash_reserve": ("num", 0, 10_000_000, "down"),
    "positions_target": ("int", 1, 100, "inmediato"),
}

PROFILE_RULES = {
    "perdida_maxima_pct": ("num", 0, 100, "up"),
    "horizonte_anios": ("num", 0, 100, "up"),
    "nivel_riesgo": ("enum", _NIVELES_RIESGO, "up"),
    "objetivo": ("text", 1, 300, "cambio"),
}

LIMITES_PENDIENTES = "limits_pendientes"
PERFIL_PENDIENTES = "risk_profile_pendientes"


class CuerdasError(Exception):
    """Entrada rechazada por las reglas de las cuerdas (400 en la API)."""


def _now():
    """Ahora consciente (UTC); las pruebas lo adelantan para madurar lotes."""
    return datetime.now(timezone.utc)


def _desde_iso(valor):
    try:
        return datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def _madurado(batch):
    if not isinstance(batch, dict):
        return False
    desde = _desde_iso(batch.get("efectivo_desde"))
    if desde is None:
        return False
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)
    return _now() >= desde


def _promover(conn, uid, setting_key, pending_key):
    """Un lote cuyo plazo venció se funde en el ajuste guardado y se limpia."""
    batch = D.get_setting(conn, uid, pending_key)
    if not _madurado(batch):
        return
    stored = D.get_setting(conn, uid, setting_key, {}) or {}
    stored.update(batch.get("cambios") or {})
    D.set_setting(conn, uid, setting_key, stored)
    conn.execute("DELETE FROM settings WHERE user_id=? AND key=?", (uid, pending_key))


def _efectivo(conn, uid, setting_key, pending_key):
    """Guardado + lote pendiente ya madurado (sin escribir: la promoción
    persistente solo ocurre en el PUT)."""
    stored = D.get_setting(conn, uid, setting_key, {}) or {}
    batch = D.get_setting(conn, uid, pending_key)
    if _madurado(batch):
        stored = {**stored, **(batch.get("cambios") or {})}
    return stored


def limites_efectivos(conn, uid):
    return {**RK.DEFAULT_LIMITS, **_efectivo(conn, uid, "limits", LIMITES_PENDIENTES)}


def perfil_efectivo(conn, uid):
    return _efectivo(conn, uid, "risk_profile", PERFIL_PENDIENTES)


def pendientes(conn, uid, pending_key):
    batch = D.get_setting(conn, uid, pending_key)
    return batch if isinstance(batch, dict) else None


def _validar(rules, body):
    """Clave → valor validado. Rechaza claves desconocidas, bool, NaN/inf y
    valores fuera de rango."""
    cambios = {}
    for k, v in body.items():
        if k == "motivo":
            continue
        rule = rules.get(k)
        if rule is None:
            return None, f"Clave no admitida: {k}"
        tipo = rule[0]
        if tipo == "num":
            if (isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v)):
                return None, f"{k} debe ser un número finito"
            if not rule[1] <= v <= rule[2]:
                return None, f"{k} fuera de rango ({rule[1]:g}–{rule[2]:g})"
            cambios[k] = v
        elif tipo == "int":
            if isinstance(v, bool) or not isinstance(v, int):
                return None, f"{k} debe ser un entero"
            if not rule[1] <= v <= rule[2]:
                return None, f"{k} fuera de rango ({rule[1]}–{rule[2]})"
            cambios[k] = v
        elif tipo == "enum":
            if v not in rule[1]:
                return None, f"{k} debe ser uno de: {', '.join(rule[1])}"
            cambios[k] = v
        elif tipo == "text":
            if not isinstance(v, str) or not rule[1] <= len(v.strip()) <= rule[2]:
                return None, f"{k} debe ser un texto de {rule[1]}–{rule[2]} caracteres"
            cambios[k] = v.strip()
    return cambios, None


def _afloja(rule, actual, nuevo):
    """¿El cambio afloja respecto al valor efectivo actual? Sin valor actual
    registrado todo aplica de inmediato."""
    tipo = rule[0]
    if tipo in ("num", "int"):
        if actual is None:
            return False
        return nuevo > actual if rule[3] == "up" else nuevo < actual
    if tipo == "enum":
        if actual not in rule[1]:
            return False
        return rule[1][nuevo] > rule[1][actual]
    if tipo == "text":
        if actual in (None, ""):
            return False
        return nuevo != actual
    return False  # preferencia de UI (positions_target): siempre inmediata


def _journal(conn, uid, tesis, review_date=""):
    data = {"tesis": tesis, "riesgos": "", "condicion_invalidacion": ""}
    conn.execute("INSERT INTO journal (user_id, ticker, action, data, review_date, created_at) "
                 "VALUES (?,?,?,?,?,?)",
                 (uid, "", "revision", json.dumps(data, ensure_ascii=False), review_date, D.now()))


def proponer(conn, uid, body, *, rules, setting_key, pending_key, nombre, defaults=None):
    """Valida el cuerpo y reparte: lo que endurece/iguala aplica ya (y sale
    del lote pendiente); lo que afloja va a un único lote con enfriamiento."""
    if not isinstance(body, dict):
        raise CuerdasError("Cuerpo inválido")
    _promover(conn, uid, setting_key, pending_key)
    cambios, error = _validar(rules, body)
    if error:
        raise CuerdasError(error)
    stored = D.get_setting(conn, uid, setting_key, {}) or {}
    efectivos = {**(defaults or {}), **stored}
    previo = pendientes(conn, uid, pending_key)
    prev_cambios = dict(previo["cambios"]) if isinstance((previo or {}).get("cambios"), dict) else {}
    aplicados, aflojan = {}, {}
    for k, v in cambios.items():
        if _afloja(rules[k], efectivos.get(k), v):
            aflojan[k] = v
        else:
            aplicados[k] = v
            prev_cambios.pop(k, None)
    motivo = body.get("motivo")
    if aflojan:
        if not isinstance(motivo, str) or not 1 <= len(motivo.strip()) <= 500:
            raise CuerdasError("Este cambio afloja tus reglas y espera "
                               f"{ENFRIAMIENTO_DIAS} días: escribe el motivo (1–500 caracteres).")
        motivo = motivo.strip()
    if aplicados:
        stored.update(aplicados)
        D.set_setting(conn, uid, setting_key, stored)
    batch = None
    if aflojan:
        ahora = _now()
        desde = ahora + timedelta(days=ENFRIAMIENTO_DIAS)
        batch = {"cambios": aflojan, "motivo": motivo,
                 "solicitado": ahora.isoformat(timespec="seconds"),
                 "efectivo_desde": desde.isoformat(timespec="seconds")}
        D.set_setting(conn, uid, pending_key, batch)
        detalle = ", ".join(f"{k}: {efectivos.get(k)} → {v}" for k, v in aflojan.items())
        _journal(conn, uid,
                 f"Cambio de {nombre} solicitado (afloja): {detalle}. "
                 f"Motivo: {motivo}. Efectivo desde {batch['efectivo_desde'][:10]}.",
                 review_date=batch["efectivo_desde"][:10])
    elif previo is not None:
        if prev_cambios:
            if prev_cambios != previo["cambios"]:
                previo = {**previo, "cambios": prev_cambios}
                D.set_setting(conn, uid, pending_key, previo)
            batch = previo
        else:
            conn.execute("DELETE FROM settings WHERE user_id=? AND key=?", (uid, pending_key))
    return {"aplicados": aplicados, "pendientes": batch}


def cancelar(conn, uid, pending_key):
    """Cancela el lote pendiente; deja constancia en el Diario."""
    batch = pendientes(conn, uid, pending_key)
    if batch is None:
        return None
    conn.execute("DELETE FROM settings WHERE user_id=? AND key=?", (uid, pending_key))
    detalle = ", ".join(f"{k}: {v}" for k, v in (batch.get("cambios") or {}).items())
    _journal(conn, uid, f"Cambio pendiente cancelado: {detalle}")
    return batch
