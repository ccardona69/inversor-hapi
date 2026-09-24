"""Autenticación con sesión por cookie y perfil del inversionista."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import db as D
from .. import decisions as DE
from ..deps import DISCLAIMER, conn_dep, current_user

router = APIRouter()


class Credentials(BaseModel):
    email: str
    password: str


@router.post("/api/register")
def register(body: Credentials, response: Response, conn=Depends(conn_dep)):
    if len(body.password) < 8:
        raise HTTPException(400, "Contraseña mínima: 8 caracteres")
    try:
        uid = D.create_user(conn, body.email, body.password)
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Correo ya registrado")
    token = D.create_session(conn, uid)
    D.audit(conn, uid, "registro", body.email)
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return {"ok": True}


@router.post("/api/login")
def login(body: Credentials, response: Response, conn=Depends(conn_dep)):
    uid = D.check_login(conn, body.email, body.password)
    if uid is None:
        raise HTTPException(401, "Credenciales incorrectas")
    token = D.create_session(conn, uid)
    response.set_cookie("session", token, httponly=True, samesite="lax")
    return {"ok": True}


@router.post("/api/logout")
def logout(request: Request, response: Response, conn=Depends(conn_dep)):
    token = request.cookies.get("session")
    if token:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/api/me")
def me(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    row = conn.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
    return {"user_id": uid, "email": row["email"], "disclaimer": DISCLAIMER}


# ---------- perfil del inversionista ----------

@router.get("/api/profile")
def profile_get(uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    return {"profile": prof, "fields": DE.RISK_PROFILE_FIELDS, **DE.profile_completeness(prof)}


@router.put("/api/profile")
def profile_put(body: dict, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    prof = D.get_setting(conn, uid, "risk_profile", {}) or {}
    prof.update(body)
    D.set_setting(conn, uid, "risk_profile", prof)
    D.audit(conn, uid, "perfil_actualizado", ", ".join(body.keys()))
    return {"ok": True, **DE.profile_completeness(prof)}
