"""Sincronización de cartera por foto: un modelo de visión lee una captura de la
app de Hapi y extrae las posiciones. El usuario SIEMPRE confirma antes de guardar:
la IA propone, no decide.

La llamada al proveedor vive en ai_provider; este módulo aporta el prompt de
extracción y el filtrado de filas.
"""
import math

from . import ai_provider as AP

# Regla del producto aplicada a la IA: no inventar. Lo que no se ve en la
# captura queda null y el usuario lo completa o lo confirma.
PROMPT = """Eres un extractor de datos. Analiza esta captura de pantalla de la app de \
inversiones Hapi (portafolio / posiciones) y devuelve las posiciones que aparecen.

Devuelve SOLO un JSON válido, sin explicaciones ni markdown, con esta forma:
{"posiciones": [{"ticker": "...", "name": "...", "qty": 0.0, "avg_cost": 0.0,
  "invested": 0.0, "value": 0.0, "pl": 0.0, "pl_pct": 0.0}], "cash": null}

Reglas estrictas:
- ticker: símbolo bursátil en MAYÚSCULAS (p. ej. NVDA, MSFT, VOO).
- Copia cada número exactamente como aparece en la captura, sin redondear ni recalcular.
- Si un dato no es visible o no distingues bien, usa null. NUNCA estimes ni inventes valores.
- qty es la cantidad de acciones (admite decimales, Hapi vende fracciones).
- avg_cost = precio promedio de compra; invested = total invertido; value = valor actual;
  pl = ganancia/pérdida no realizada (usa negativo si es pérdida); pl_pct = en porcentaje.
- Si la captura no muestra posiciones, devuelve {"posiciones": [], "cash": null}."""


class PhotoSyncError(Exception):
    """Fallo al analizar la captura: configuración ausente, red o respuesta inválida."""


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        number = float(v)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def normalize_rows(raw_rows):
    """Filtra lo que la IA devolvió: solo filas con ticker y cantidad > 0 pasan;
    todo número no numérico se convierte en null (nunca se adivina)."""
    rows, omitted = [], []
    for r in raw_rows or []:
        if not isinstance(r, dict):
            omitted.append({"fila": r, "motivo": "fila no reconocida"})
            continue
        tk = str(r.get("ticker") or "").upper().strip()
        qty = _num(r.get("qty"))
        if not tk or not qty or qty <= 0:
            omitted.append({"fila": r, "motivo": "ticker vacío o cantidad no válida"})
            continue
        rows.append({
            "ticker": tk, "name": str(r.get("name") or ""), "qty": qty,
            "avg_cost": _num(r.get("avg_cost")), "invested": _num(r.get("invested")),
            "hapi_value": _num(r.get("value")), "hapi_pl": _num(r.get("pl")),
            "hapi_return_pct": _num(r.get("pl_pct")),
        })
    return rows, omitted


def analyze(image_b64, mime, env=None, client=None):
    try:
        # Sin validate_image: esta vía es anterior al límite de 6 MB y la captura
        # llega ya sin el prefijo data:; se conserva su comportamiento original.
        parsed, model = AP.request(
            "Devuelves únicamente JSON válido, sin comentarios.",
            PROMPT, image_b64=image_b64, mime=mime, env=env, client=client,
            json_reply=True, temperature=0, validate_image=False)
    except AP.AIProviderError as exc:
        raise PhotoSyncError(str(exc)) from exc
    rows, omitted = normalize_rows(parsed.get("posiciones"))
    return {"rows": rows, "omitted": omitted, "cash": _num(parsed.get("cash")),
            "model": model}
