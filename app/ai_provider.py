"""Capa única de acceso a la IA (Luna) para visión y texto, sin persistencia ni
credenciales en el cliente.

Aquí vive toda la plomería del proveedor: configuración (clave, URL, modelo y
estilo de API), construcción del endpoint, armado del cuerpo y extracción de la
respuesta. Los módulos de extracción (photosync, fundsync, tradesync) y de
revisión (ai_review, ai_assistant) llaman a request(); ninguno habla con el
proveedor por su cuenta.

La configuración vive fuera del código y fuera de Git: variable de entorno
INVERSOR_AI_* o el archivo .secrets/ai.env (gitignoreado). Nunca se leen
credenciales de otras carpetas del sistema.
"""
import base64
import binascii
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

APP_ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = APP_ROOT / ".secrets" / "ai.env"
DEFAULT_API_VERSION = "2024-06-01"

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


class AIProviderError(Exception):
    """Configuración o respuesta inválida del proveedor de IA."""


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


def endpoint(cfg):
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


def extract_reply_text(data):
    text = data.get("output_text")
    if text:
        return text
    partes = []
    for item in data.get("output") or []:
        for bloque in item.get("content") or []:
            if isinstance(bloque, dict) and bloque.get("text"):
                partes.append(bloque["text"])
    return "\n".join(partes) if partes else None


def parse_json_reply(content):
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


def image_input(image_b64, mime):
    """Acepta solo imágenes pequeñas; nunca guarda los bytes recibidos."""
    if mime not in ALLOWED_MIME:
        raise AIProviderError("Usa una imagen JPEG, PNG o WebP")
    image = image_b64 or ""
    if not isinstance(image, str):
        raise AIProviderError("No se recibió una imagen válida")
    if image.startswith("data:"):
        prefix, sep, image = image.partition(",")
        if not sep or prefix != f"data:{mime};base64":
            raise AIProviderError("El tipo de imagen no coincide con el archivo")
    try:
        if not image or len(image) > (MAX_IMAGE_BYTES + 2) * 4 // 3 + 4:
            raise AIProviderError("La imagen está vacía o supera los 6 MB")
        raw = base64.b64decode(image, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AIProviderError("La imagen no tiene un formato base64 válido") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise AIProviderError("La imagen está vacía o supera los 6 MB")
    return f"data:{mime};base64,{image}"


def request(instructions, user_text, *, image_b64=None, mime=None, env=None, client=None,
            max_tokens=2048, json_reply=False, temperature=None, validate_image=True):
    cfg = load_config(env)
    if not all(cfg[k] for k in ("api_key", "base_url", "model")):
        raise AIProviderError("IA no configurada: revisa INVERSOR_AI_API_KEY, "
                              "INVERSOR_AI_BASE_URL e INVERSOR_AI_MODEL")
    url, headers, style = endpoint(cfg)
    if image_b64 is None:
        image_url = None
    elif validate_image:
        image_url = image_input(image_b64, mime)
    else:
        image_url = f"data:{mime};base64,{image_b64}"
    if json_reply:
        instructions += "\nResponde solo con un objeto JSON válido, sin markdown ni comentarios."
    if style == "responses":
        content = [{"type": "input_text", "text": user_text}]
        if image_url:
            content.append({"type": "input_image", "image_url": image_url, "detail": "auto"})
        body = {"model": cfg["model"], "instructions": instructions,
                "input": [{"role": "user", "content": content}], "max_output_tokens": max_tokens}
    else:
        content = user_text if not image_url else [{"type": "text", "text": user_text},
                                                   {"type": "image_url", "image_url": {"url": image_url}}]
        body = {"model": cfg["model"], "messages": [{"role": "system", "content": instructions},
                                                    {"role": "user", "content": content}],
                "max_tokens": max_tokens}
    if temperature is not None:
        # Los modelos de razonamiento (GPT-5, o3, o4) rechazan temperature en la
        # superficie Responses; el resto la acepta en ambas superficies.
        reasoning = cfg["model"].lower().startswith(("gpt-5", "o3", "o4"))
        if not (reasoning and style == "responses"):
            body["temperature"] = temperature
    try:
        if client is None:
            with httpx.Client(timeout=120) as http:
                response = http.post(url, headers=headers, json=body)
        else:
            response = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise AIProviderError("No se pudo contactar al servicio de IA") from exc
    if response.status_code in (401, 403):
        raise AIProviderError("El servicio de IA rechazó la clave configurada")
    if response.status_code >= 400:
        raise AIProviderError(f"El servicio de IA devolvió el estado {response.status_code}")
    try:
        payload = response.json()
        reply = extract_reply_text(payload) if style == "responses" else payload["choices"][0]["message"]["content"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("respuesta vacía")
        answer = parse_json_reply(reply) if json_reply else reply.strip()
        if json_reply and not isinstance(answer, dict):
            raise ValueError("se esperaba un objeto")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise AIProviderError("La IA no devolvió una respuesta interpretable; vuelve a intentarlo") from exc
    return answer, cfg["model"]
