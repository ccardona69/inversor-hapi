"""Consultas a Luna (sin modificar la cartera)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import ai_assistant as AI
from ..deps import conn_dep, current_user
from .decisions import risk_get
from .portfolio import enrich_positions

router = APIRouter()


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=600)


@router.post("/api/assistant/ask")
def assistant_ask(body: AssistantQuestion, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Escribe una pregunta para Luna")
    positions = enrich_positions(conn, uid)
    risk = risk_get(uid, conn)
    context = AI.context_for_user(conn, uid, positions, risk)
    try:
        return AI.ask(question, context)
    except AI.AssistantError as e:
        raise HTTPException(502, str(e)) from e
