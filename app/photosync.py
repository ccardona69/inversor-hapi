"""Sincronización de cartera por foto: un modelo de visión lee una captura de la
app de Hapi y extrae las posiciones. El usuario SIEMPRE confirma antes de guardar:
la IA propone, no decide.

Proveedores soportados (protocolo OpenAI): Azure AI Foundry estilo «Responses»
(p. ej. GPT-5.6-Luna) y el estilo «Chat Completions» (Azure clásico, OpenAI,
OpenRouter, etc.). La clave vive fuera del código y fuera de Git: variable de
entorno INVERSOR_AI_API_KEY o el archivo .secrets/ai.env (gitignoreado).
Nunca se leen credenciales de otras carpetas del sistema.
"""
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

APP_ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = APP_ROOT / ".secrets" / "ai.env"
DEFAULT_API_VERSION = "2024-06-01"

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


def _parse_env_file(path: Path):
    out = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def load_config(env=None):
    env = os.environ if env is None else env
    file_cfg = _parse_env_file(SECRETS_FILE)

    def pick(name):
        v = (env.get(name) or "").strip()
        return v or (file_cfg.get(name) or "").strip()

    return {
        "api_key": pick("INVERSOR_AI_API_KEY"),
        "base_url": pick("INVERSOR_AI_BASE_URL"),
        "model": pick("INVERSOR_AI_MODEL"),
        # responses = Azure Foundry / GPT-5 (input + instructions); chat = chat/completions
        "api_style": (pick("INVERSOR_AI_API_STYLE") or "chat").lower(),
        "api_version": pick("INVERSOR_AI_API_VERSION") or DEFAULT_API_VERSION,
    }


def config_status(env=None):
    cfg = load_config(env)
    from_env = bool((os.environ.get("INVERSOR_AI_API_KEY") or "").strip())
    configured = bool(cfg["api_key"] and cfg["base_url"] and cfg["model"])
    return {
        "configured": configured,
        "key_source": ("variable de entorno" if from_env else ".secrets/ai.env") if configured else None,
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_style": cfg["api_style"],
        "hint": "" if configured else
        "Configura INVERSOR_AI_API_KEY, INVERSOR_AI_BASE_URL e INVERSOR_AI_MODEL "
        f"(env o {SECRETS_FILE}) y reinicia el servidor.",
    }


def _endpoint(cfg):
    base = cfg["base_url"].strip().rstrip("/")
    # Igual que hace el bot del voucher: si se pegó el host o la URL de una
    # operación, se recorta/completa a la base sin la operación final.
    for sufijo in ("/responses", "/chat/completions"):
        if base.endswith(sufijo):
            base = base[: -len(sufijo)]

    headers = {"api-key": cfg["api_key"], "Authorization": f"Bearer {cfg['api_key']}",
               "Content-Type": "application/json"}
    op = "/responses" if cfg["api_style"] == "responses" else "/chat/completions"

    if "openai.azure.com" in base:
        # Recurso clásico de Azure OpenAI: el deployment va en la ruta.
        if cfg["api_style"] == "responses":
            url = f"{base}/openai/v1{op}"
        else:
            url = f"{base}/openai/deployments/{cfg['model']}{op}"
            url += ("&" if "?" in url else "?") + f"api-version={cfg['api_version']}"
        return url, headers, cfg["api_style"]

    # Foundry y genéricos: la base ya trae /openai/v1 o /v1; si solo pegaron el
    # host, se completa con la raíz estándar.
    path = urlparse(base).path
    if path in ("", "/"):
        base += "/openai/v1" if cfg["api_style"] == "responses" else "/v1"
    elif base.count("/") == 2:  # host sin raíz de API
        base += "/openai/v1" if cfg["api_style"] == "responses" else "/v1"
    return base + op, headers, cfg["api_style"]


def _extract_reply_text(data):
    text = data.get("output_text")
    if text:
        return text
    partes = []
    for item in data.get("output") or []:
        for bloque in item.get("content") or []:
            if isinstance(bloque, dict) and bloque.get("text"):
                partes.append(bloque["text"])
    return "\n".join(partes) if partes else None


def _parse_json_reply(content):
    text = (content or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


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


def _body_chat(cfg, mime, image_b64):
    return {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "Devuelves únicamente JSON válido, sin comentarios."},
            {"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            ]},
        ],
        "max_tokens": 2048,
        "temperature": 0,
    }


def _body_responses(cfg, mime, image_b64):
    # Superficie Responses (la que usa Luna): instructions/input/max_output_tokens
    # y partes input_text/input_image. Sin temperature si es GPT-5 con razonamiento.
    body = {
        "model": cfg["model"],
        "instructions": "Devuelves únicamente JSON válido, sin comentarios.",
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": f"data:{mime};base64,{image_b64}", "detail": "auto"},
            ],
        }],
        "max_output_tokens": 2048,
    }
    if cfg["model"].lower().startswith(("gpt-5", "o3", "o4")):
        body.pop("temperature", None)
    else:
        body["temperature"] = 0
    return body


def analyze(image_b64, mime, env=None, client=None):
    cfg = load_config(env)
    if not (cfg["api_key"] and cfg["base_url"] and cfg["model"]):
        raise PhotoSyncError("IA no configurada: faltan INVERSOR_AI_API_KEY, "
                             "INVERSOR_AI_BASE_URL o INVERSOR_AI_MODEL")
    url, headers, style = _endpoint(cfg)
    body = _body_responses(cfg, mime, image_b64) if style == "responses" else _body_chat(cfg, mime, image_b64)
    try:
        if client is None:
            with httpx.Client(timeout=120) as hc:
                resp = hc.post(url, headers=headers, json=body)
        else:
            resp = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        raise PhotoSyncError(f"No se pudo contactar el servicio de IA: {e}") from e
    if resp.status_code in (401, 403):
        raise PhotoSyncError("El servicio de IA rechazó la clave (revisa INVERSOR_AI_API_KEY)")
    if resp.status_code >= 400:
        raise PhotoSyncError(f"El servicio de IA devolvió {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
        content = _extract_reply_text(data) if style == "responses" \
            else data["choices"][0]["message"]["content"]
        parsed = _parse_json_reply(content)
        raw = parsed.get("posiciones")
    except (KeyError, IndexError, ValueError, json.JSONDecodeError, TypeError) as e:
        raise PhotoSyncError("La IA no devolvió un JSON interpretable. Vuelve a intentar "
                             "con una captura más nítida o completa.") from e
    rows, omitted = normalize_rows(raw)
    return {"rows": rows, "omitted": omitted, "cash": _num(parsed.get("cash")),
            "model": cfg["model"]}
