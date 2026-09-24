"""Acceso acotado a Luna para visión y texto, sin persistencia ni credenciales en el cliente."""
import base64
import binascii
import json

import httpx

from . import photosync as PS

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


class AIProviderError(Exception):
    """Configuración o respuesta inválida del proveedor de IA."""


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
            max_tokens=2048, json_reply=False):
    cfg = PS.load_config(env)
    if not all(cfg[k] for k in ("api_key", "base_url", "model")):
        raise AIProviderError("IA no configurada: revisa INVERSOR_AI_API_KEY, "
                              "INVERSOR_AI_BASE_URL e INVERSOR_AI_MODEL")
    url, headers, style = PS._endpoint(cfg)
    image_url = image_input(image_b64, mime) if image_b64 is not None else None
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
        reply = PS._extract_reply_text(payload) if style == "responses" else payload["choices"][0]["message"]["content"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("respuesta vacía")
        answer = PS._parse_json_reply(reply) if json_reply else reply.strip()
        if json_reply and not isinstance(answer, dict):
            raise ValueError("se esperaba un objeto")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise AIProviderError("La IA no devolvió una respuesta interpretable; vuelve a intentarlo") from exc
    return answer, cfg["model"]
