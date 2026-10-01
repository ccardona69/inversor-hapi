"""Consultas a Luna (sin modificar la cartera)."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import ai_assistant as AI
from .. import db as D
from ..deps import conn_dep, current_user
from .decisions import alerts, risk_get
from .marcador import estado_plan
from .portfolio import enrich_positions

router = APIRouter()


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    history: list[Turn] = Field(default_factory=list, max_length=8)


@router.post("/api/assistant/ask")
def assistant_ask(body: AssistantQuestion, uid: int = Depends(current_user), conn=Depends(conn_dep)):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Escribe una pregunta para Luna")
    plan = estado_plan(conn, uid)
    history = [t.model_dump() for t in body.history]
    # Regla del plan: con el ETF bajo la meta la respuesta es determinista y no
    # se llama al proveedor; la respuesta del usuario fuera de plan queda en el
    # Diario con sus palabras.
    guard = AI.plan_guard(question, plan)
    if guard:
        return {"answer": guard, "model": AI.PLAN_GUARD_MODEL,
                "asof": D.now(), "plan_guard": True}
    if AI.plan_guard_followup(question, history):
        ticker = AI.plan_guard_ticker(history)
        data = {"ticker": ticker or "", "action": "revision",
                "tesis": "Fuera de plan — " + AI.PLAN_GUARD_QUESTION +
                         f" Respuesta del usuario: {question}",
                "riesgos": "", "condicion_invalidacion": ""}
        conn.execute("INSERT INTO journal (user_id, ticker, action, data, review_date, created_at) "
                     "VALUES (?,?,?,?,?,?)",
                     (uid, ticker, "revision", json.dumps(data, ensure_ascii=False), "", D.now()))
        return {"answer": "Guardé tu respuesta en el Diario con tus palabras.",
                "model": AI.PLAN_GUARD_MODEL, "asof": D.now(), "plan_guard": True}
    positions = enrich_positions(conn, uid)
    risk = risk_get(uid, conn)
    context = AI.context_for_user(conn, uid, positions, risk, alerts(uid, conn)["alerts"],
                                  plan={"etf_pct": plan["etf_pct"],
                                        "etf_target_pct": plan["etf_target_pct"],
                                        "regla": AI.PLAN_GUARD_REGLA})
    try:
        return AI.ask(question, context, history=history)
    except AI.AssistantError as e:
        raise HTTPException(502, str(e)) from e
