"""Módulo 7: motor de decisiones explicables.

Compara las alternativas (comprar, agregar, mantener, reducir, vender, esperar,
sustituir, efectivo) con argumentos a favor/en contra basados SOLO en datos
disponibles. Reglas duras:
- El costo promedio nunca es la razón principal de una decisión.
- No se recomienda comprar solo porque la posición está en rojo.
- Sin perfil de riesgo completo, la salida es informativa, no personalizada.
- Siempre se analiza desde el presente («¿la compraríamos hoy?»).
"""

ACTIONS = ["comprar", "agregar_gradualmente", "mantener", "reducir", "vender", "esperar",
           "sustituir", "mantener_efectivo"]

RISK_PROFILE_FIELDS = [
    "capital_total", "capital_disponible", "aporte_mensual", "fondo_emergencia", "moneda",
    "horizonte_anios", "objetivo", "rentabilidad_esperada_pct", "perdida_maxima_pct",
    "necesita_retirar", "experiencia", "nivel_riesgo", "ingresos_estables",
    "max_por_empresa_pct", "max_por_sector_pct", "prefiere_fondos", "restricciones", "comisiones_impuestos",
]


def profile_completeness(profile: dict) -> dict:
    missing = [f for f in RISK_PROFILE_FIELDS if profile.get(f) in (None, "")]
    return {"complete": not missing, "missing": missing}


def averaging_down_checklist(ctx: dict) -> list:
    """Preguntas obligatorias antes de agregar capital a una posición en pérdida.
    El motor responde las que puede con datos; el resto queda para el usuario."""
    mos = ctx.get("margin_of_safety_pct")
    weight = ctx.get("weight_pct")
    max_w = ctx.get("max_position_pct", 25)
    items = [
        ("¿La tesis sigue vigente?", "Sí, hay una tesis registrada y sin invalidación" if ctx.get("has_thesis")
         else "SIN RESPONDER: no hay tesis registrada en el diario — regístrala antes de agregar"),
        ("¿El negocio mejoró o se deterioró?", "Revisa los últimos resultados en Fundamentales"
         if not ctx.get("fundamentals") else "Hay fundamentales registrados: compáralos con el trimestre previo"),
        ("¿La valoración ofrece margen de seguridad?",
         f"Escenario base: {mos:+.1f}%" if mos is not None else "SIN CALCULAR: faltan FCF/acciones para el DCF"),
        ("¿Se intenta comprar solamente para bajar el promedio?",
         "ADVERTENCIA: la posición está en pérdida; verifica que el motivo sea la tesis y no el precio de entrada"
         if (ctx.get("unrealized_pl") or 0) < 0 else "La posición no está en pérdida"),
        ("¿La posición ya es demasiado grande?",
         f"Pesa {weight:.1f}% (límite configurado: {max_w}%) — {'EXCEDE el límite' if weight and weight > max_w else 'dentro del límite'}"
         if weight is not None else "Peso no calculable"),
        ("¿Existe una oportunidad mejor?", "Compara en el Buscador de oportunidades"),
        ("¿Puedes soportar una caída adicional?", "Revisa el simulador de escenarios (-10/-20/-30%)"),
        ("¿El horizonte es suficiente?", f"Horizonte declarado: {ctx.get('horizonte', 'SIN REGISTRAR')}"),
        ("¿Hay resultados financieros próximos?", ctx.get("next_earnings") or "Fecha de próximos resultados no registrada"),
        ("¿Qué pasaría si cae 10/20/30% más?", "Ver simulador — las cifras están en la pestaña Escenarios"),
    ]
    return [{"pregunta": q, "respuesta": a} for q, a in items]


def evaluate_position(ctx: dict) -> dict:
    """Genera la comparación de alternativas y una decisión propuesta.

    ctx: ticker, price, price_status, qty, market_value, invested, avg_cost, unrealized_pl,
         weight_pct, max_position_pct, margin_of_safety_pct (o None), fundamentals(bool),
         has_thesis(bool), technical(dict|None), profile_complete(bool), data_quality(list)
    """
    options = {a: {"a_favor": [], "en_contra": [], "condiciones": []} for a in ACTIONS}
    w, max_w = ctx.get("weight_pct"), ctx.get("max_position_pct", 25)
    mos = ctx.get("margin_of_safety_pct")
    over = w is not None and w > max_w

    if over:
        options["reducir"]["a_favor"].append(
            f"La posición pesa {w:.1f}%, por encima de tu límite de {max_w}%: reducir baja el riesgo de concentración")
        options["agregar_gradualmente"]["en_contra"].append("Agregaría concentración a una posición ya sobredimensionada")
        options["comprar"]["en_contra"].append("La posición ya excede tu límite por empresa")
    else:
        options["reducir"]["en_contra"].append("El peso está dentro de tus límites configurados")

    if mos is not None:
        if mos > 20:
            options["agregar_gradualmente"]["a_favor"].append(
                f"El escenario base del DCF sugiere margen de seguridad de {mos:.0f}% (con tus supuestos)")
            options["agregar_gradualmente"]["condiciones"].append("Solo si la tesis está registrada y el peso lo permite")
        elif mos < -20:
            options["reducir"]["a_favor"].append(
                f"El escenario base sugiere que el precio excede el valor estimado en {-mos:.0f}% (con tus supuestos)")
            options["esperar"]["a_favor"].append("Esperar un precio con margen de seguridad")
        else:
            options["mantener"]["a_favor"].append("La valoración base está cerca del precio: sin señal fuerte en ningún sentido")
    else:
        options["esperar"]["a_favor"].append("Faltan datos de valoración: la opción prudente es no actuar hasta completarlos")
        options["agregar_gradualmente"]["en_contra"].append("Sin valoración calculable no hay evidencia para agregar")
        options["vender"]["en_contra"].append("Sin valoración calculable tampoco hay evidencia para vender")

    if (ctx.get("unrealized_pl") or 0) < 0:
        options["vender"]["en_contra"].append(
            "Vender solo por estar en rojo es vender por miedo; evalúa la tesis, no el costo promedio")
        options["agregar_gradualmente"]["en_contra"].append(
            "Comprar solo para bajar el promedio no es una tesis; responde el checklist de promediar")
    if not ctx.get("has_thesis"):
        options["mantener"]["condiciones"].append("Registra una tesis con condición de invalidación en el Diario")
        options["agregar_gradualmente"]["en_contra"].append("No hay tesis registrada para esta posición")

    tech = ctx.get("technical") or {}
    if tech.get("rsi14") and tech["rsi14"] > 70:
        options["comprar"]["en_contra"].append(f"RSI {tech['rsi14']} en zona de sobrecompra (dato complementario)")
    if tech.get("rsi14") and tech["rsi14"] < 30:
        options["esperar"]["condiciones"].append(f"RSI {tech['rsi14']} en sobreventa: si la tesis es válida, posible entrada escalonada")

    options["mantener_efectivo"]["a_favor"].append("El efectivo conserva opcionalidad para mejores precios")
    options["mantener_efectivo"]["en_contra"].append("Pierde poder adquisitivo frente a la inflación a largo plazo")
    options["sustituir"]["condiciones"].append("Solo con un candidato del Buscador con mejor riesgo/retorno documentado")

    # Decisión propuesta (heurística transparente)
    if over and mos is not None and mos < 0:
        decision, conf = "reducir", "media"
        args = ["Exceso de concentración y valoración sin margen de seguridad con los supuestos actuales"]
    elif over:
        decision, conf = "reducir", "baja"
        args = [f"El peso ({w:.1f}%) excede tu límite ({max_w}%); reducir gradualmente hasta el límite. "
                "La valoración no es concluyente: decide el tamaño, no el precio."]
    elif mos is None or not ctx.get("fundamentals"):
        decision, conf = "esperar", "baja"
        args = ["Faltan fundamentales/valoración: completa los datos antes de mover capital"]
    elif mos > 20 and ctx.get("has_thesis"):
        decision, conf = "agregar_gradualmente", "media"
        args = [f"Margen de seguridad estimado {mos:.0f}% y tesis vigente; entrar escalonado, nunca de golpe"]
    elif mos < -25:
        decision, conf = "reducir", "media"
        args = [f"El precio supera el valor estimado en {-mos:.0f}% en el escenario base"]
    else:
        decision, conf = "mantener", "media"
        args = ["Sin señal fuerte de valoración ni incumplimiento de límites: mantener y revisar en la próxima fecha"]

    if not ctx.get("profile_complete"):
        conf = "baja"
        args.append("AVISO: tu perfil de inversionista está incompleto; esta salida es informativa, no una recomendación personalizada")
    if ctx.get("price_status") != "actual":
        args.append(f"AVISO: el precio usado no es de hoy (estado: {ctx.get('price_status')}); actualízalo antes de decidir")

    return {
        "pregunta_obligatoria": "Si hoy toda esta posición estuviera en efectivo, ¿la comprarías nuevamente al precio y tamaño actuales?",
        "alternativas": options,
        "decision_propuesta": decision,
        "argumentos": args,
        "nivel_confianza": conf,
        "checklist_promediar": averaging_down_checklist(ctx) if (ctx.get("unrealized_pl") or 0) < 0 else None,
        "nota": "Apoyo a la decisión, no asesoría financiera regulada. Ninguna operación se ejecuta automáticamente.",
    }


def simulate(positions: list, cash: float, changes: dict, trades: list) -> dict:
    """Módulo 9: simulador. changes: {ticker: variación_%}; trades: [{ticker, side, amount_usd}]."""
    sim = {p["ticker"]: dict(p) for p in positions}
    sim_cash = cash or 0.0
    assumptions = []
    for t in trades or []:
        tk, amt = t["ticker"].upper(), float(t.get("amount_usd") or 0)
        if t.get("side") == "comprar":
            if amt > sim_cash:
                assumptions.append(f"Compra de {tk} recortada al efectivo disponible ({sim_cash:.2f})")
                amt = sim_cash
            sim_cash -= amt
            if tk in sim:
                sim[tk]["market_value"] = (sim[tk].get("market_value") or 0) + amt
            else:
                sim[tk] = {"ticker": tk, "market_value": amt, "invested": amt, "sector": None}
            assumptions.append(f"Compra simulada de {amt:.2f} USD en {tk} (sin comisiones ni impuestos, salvo que los configures)")
        else:
            have = sim.get(tk, {}).get("market_value") or 0
            if have <= 0:
                # No se puede vender lo que no se tiene (o cuyo valor es cero): se ignora
                # en vez de crashear con KeyError al indexar una posición inexistente.
                assumptions.append(f"Venta simulada de {tk} ignorada: no tienes esa posición o su valor es cero")
                continue
            amt = min(amt, have)
            sim[tk]["market_value"] = have - amt
            sim_cash += amt
            assumptions.append(f"Venta simulada de {amt:.2f} USD en {tk}")
    for tk, pct in (changes or {}).items():
        tk = tk.upper()
        if tk in sim and sim[tk].get("market_value"):
            sim[tk]["market_value"] = sim[tk]["market_value"] * (1 + float(pct) / 100)
            assumptions.append(f"{tk}: variación simulada de {float(pct):+.1f}%")
    final_positions = [p for p in sim.values() if (p.get("market_value") or 0) > 0.005]
    total = sum(p["market_value"] for p in final_positions) + sim_cash
    costs_complete = all(p.get("invested") is not None for p in final_positions)
    invested = sum(p.get("invested") or 0 for p in final_positions)
    weights = [{"ticker": p["ticker"], "peso_pct": round(p["market_value"] / total * 100, 2)}
               for p in final_positions] if total > 0 else []
    hhi = round(sum(w["peso_pct"] ** 2 for w in weights)) if weights else 0
    return {
        "valor_final_estimado": round(total, 2), "efectivo_final": round(sim_cash, 2),
        "resultado_vs_invertido": round(total - invested - sim_cash, 2) if invested and costs_complete else None,
        "concentracion_resultante": weights, "hhi_resultante": hhi,
        "supuestos": assumptions or ["Sin cambios aplicados"],
        "nota": "Simulación aritmética sobre tus datos; no es una predicción de mercado.",
    }
