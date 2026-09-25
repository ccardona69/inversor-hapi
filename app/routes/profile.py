"""Perfil de riesgo del inversionista (app local de un solo usuario, sin login)."""
from fastapi import APIRouter, Depends

from .. import db as D
from .. import decisions as DE
from ..deps import conn_dep, current_user

router = APIRouter()


@router.get("/api/profile")
def profile_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    return {"profile": prof, "fields": DE.RISK_PROFILE_FIELDS, **DE.profile_completeness(prof)}


@router.put("/api/profile")
def profile_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    prof.update(body)
    D.set_setting(conn, uid, "risk_profile", prof)
    return {"ok": True, **DE.profile_completeness(prof)}
