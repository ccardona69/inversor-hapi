"""Configuración de límites y borrado total de datos."""
import json
import os
import subprocess

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


_version_cache: dict | None = None


@router.get("/api/system/version")
def system_version():
    """Tag/hash del código desplegado, leído del checkout en disco (git describe).
    Si no hay repo git o falla, se declara SIN DATO en vez de inventar."""
    global _version_cache
    if _version_cache is None:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            r = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                               cwd=repo, capture_output=True, text=True, timeout=5)
            v = r.stdout.strip() if r.returncode == 0 else ""
            _version_cache = {"version": v or None, "fuente": "git describe --tags --always --dirty",
                              "fecha_lectura": D.now(),
                              "etiqueta": "HV" if v else "SIN DATO"}
        except Exception:
            _version_cache = {"version": None, "fuente": "git describe",
                              "fecha_lectura": D.now(), "etiqueta": "SIN DATO"}
    return _version_cache


@router.get("/api/system/export")
def system_export(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Volcado JSON legible de todos los datos del usuario: respaldo portable
    que no depende de la app para leerse."""
    return {"exported_at": D.now(), "tables": D.export_data(conn, uid)}


@router.post("/api/settings/delete_all")
def delete_all(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    if body.get("confirm") != "ELIMINAR":
        raise HTTPException(400, 'Escribe "ELIMINAR" en confirm')
    backup = D.backup_db()  # nunca borrar sin respaldo previo (G0)
    for t in ("positions", "fundamentals", "journal", "decisions",
              "candidates", "settings", "cash", "trades", "trade_sources",
              "contributions"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    return {"ok": True, "detail": "Datos eliminados", "backup": backup}

