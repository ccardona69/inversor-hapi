"""Configuración de límites, auditoría y borrado total de datos."""
import json

from fastapi import APIRouter, Depends, HTTPException

from .. import db as D
from .. import risk as RK
from ..deps import conn_dep, current_user

router = APIRouter()


@router.get("/api/settings")
def settings_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return {"limits": {**RK.DEFAULT_LIMITS, **(D.get_setting(conn, uid, "limits", {}) or {})}}


@router.get("/api/audit")
def audit_list(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    rows = conn.execute("SELECT * FROM audit_log WHERE user_id=? ORDER BY id DESC LIMIT 200", (uid,)).fetchall()
    return {"log": [dict(r) for r in rows]}


@router.post("/api/settings/delete_all")
def delete_all(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if body.get("confirm") != "ELIMINAR":
        raise HTTPException(400, 'Escribe "ELIMINAR" en confirm')
    for t in ("positions", "trade_sources", "trades", "fundamentals", "journal", "decisions",
              "candidates", "settings", "audit_log", "cash"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados"}
