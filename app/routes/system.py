"""Configuración de límites y borrado total de datos."""
import json

from fastapi import APIRouter, Depends, HTTPException

from .. import db as D
from .. import risk as RK
from ..deps import conn_dep, current_user

router = APIRouter()


@router.get("/api/settings")
def settings_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return {"limits": {**RK.DEFAULT_LIMITS, **(D.get_setting(conn, uid, "limits", {}) or {})}}


@router.post("/api/settings/delete_all")
def delete_all(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if body.get("confirm") != "ELIMINAR":
        raise HTTPException(400, 'Escribe "ELIMINAR" en confirm')
    for t in ("positions", "fundamentals", "journal", "decisions",
              "candidates", "settings", "cash", "trades", "trade_sources"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados"}

