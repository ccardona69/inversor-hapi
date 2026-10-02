"""Configuración de límites y borrado total de datos."""
import json

from fastapi import APIRouter, Depends, HTTPException

from .. import db as D
from .. import risk as RK
from .. import scoreboard as SB
from ..deps import conn_dep, current_user

router = APIRouter()


@router.get("/api/settings")
def settings_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    return {"limits": {**RK.DEFAULT_LIMITS, **(D.get_setting(conn, uid, "limits", {}) or {})},
            "etf_plan": D.get_setting(conn, uid, "etf_plan", SB.SETTINGS_DEFAULTS["etf_plan"]),
            "etf_target_pct": D.get_setting(conn, uid, "etf_target_pct",
                                            SB.SETTINGS_DEFAULTS["etf_target_pct"])}


@router.post("/api/system/backup")
def system_backup():
    """Snapshot íntegro de la base en backups/ (rotación de 10)."""
    dest = D.backup_db()
    if dest is None:
        raise HTTPException(404, "No existe base de datos que respaldar")
    return {"ok": True, "backup": dest}


@router.get("/api/system/export")
def system_export(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Volcado JSON legible de todos los datos del usuario: respaldo portable
    que no depende de la app para leerse."""
    return {"exported_at": D.now(), "tables": D.export_data(conn, uid)}


@router.post("/api/settings/delete_all")
def delete_all(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if body.get("confirm") != "ELIMINAR":
        raise HTTPException(400, 'Escribe "ELIMINAR" en confirm')
    for t in ("positions", "fundamentals", "journal", "decisions",
              "candidates", "settings", "cash", "trades", "trade_sources",
              "contributions"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados"}

