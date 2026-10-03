"""Perfil de riesgo del inversionista (app local de un solo usuario, sin login)."""
from fastapi import APIRouter, Depends, HTTPException

from .. import cuerdas as CU
from .. import decisions as DE
from ..deps import conn_dep, current_user

router = APIRouter()


@router.get("/api/profile")
def profile_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = CU.perfil_efectivo(conn, uid)
    return {"profile": prof, "fields": DE.RISK_PROFILE_FIELDS,
            "pendientes": CU.pendientes(conn, uid, CU.PERFIL_PENDIENTES),
            **DE.profile_completeness(prof)}


@router.put("/api/profile")
def profile_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    """Cuerdas: endurecer o el primer valor aplica ya; aflojar el perfil
    espera 7 días con motivo en el Diario."""
    try:
        res = CU.proponer(conn, uid, body, rules=CU.PROFILE_RULES,
                          setting_key="risk_profile", pending_key=CU.PERFIL_PENDIENTES,
                          nombre="perfil")
    except CU.CuerdasError as exc:
        raise HTTPException(400, str(exc)) from exc
    prof = CU.perfil_efectivo(conn, uid)
    return {"ok": True, **res, "profile": prof, **DE.profile_completeness(prof)}


@router.delete("/api/profile/pendientes")
def profile_pendientes_delete(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    batch = CU.cancelar(conn, uid, CU.PERFIL_PENDIENTES)
    if batch is None:
        raise HTTPException(404, "No hay cambio de perfil pendiente")
    return {"ok": True, "cancelado": batch}
