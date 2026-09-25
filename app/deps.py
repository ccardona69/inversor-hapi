"""Dependencias, helpers y constantes compartidas por los routers de la API."""
from fastapi import Depends, HTTPException

from . import ai_provider as AP
from . import db as D

DISCLAIMER = ("Herramienta de apoyo a decisiones con datos aportados por el usuario y fuentes públicas. "
              "No es asesoría financiera regulada ni garantiza rentabilidad.")


def conn_dep():
    conn = D.get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def current_user(conn=Depends(conn_dep)) -> int:
    # App local de un solo usuario: sin login, todo opera sobre el usuario local.
    return D.local_user_id(conn)


def _photo_input(body):
    try:
        AP.image_input(body.get("image_b64"), body.get("mime"))
    except AP.AIProviderError as exc:
        raise HTTPException(400, str(exc)) from exc
    return body["image_b64"], body["mime"]
