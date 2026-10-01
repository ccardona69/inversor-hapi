"""Entrada de flujos de dinero (Fase 1): depósitos, retiros, dividendos y
ahorro en soles contados en una frase, pegando el historial de Hapi o con una
captura. La IA propone filas; el usuario siempre confirma antes de guardar.

- «Terminado» es el único estado que entra: Creado/Cancelado/Expirado y todo lo
  demás va a omitted con su motivo.
- fingerprint detecta duplicados (sin `source`: lo mismo visto por captura y
  por texto choca); no prueba identidad ni bloquea nada por sí solo.
"""
import math
import re
import unicodedata
from datetime import date
from decimal import Decimal

from . import ai_provider as AP

# Regla del producto aplicada a la IA: no inventar. Lo que no se ve queda null.
PROMPT = """Eres Luna, extractor estricto del historial de movimientos de Hapi.
Lee solo los movimientos de dinero visibles en la captura o el texto pegado:
depósitos, retiros y dividendos. Las compras y ventas de acciones NO son
movimientos de dinero para esta lista; van a omitted con su motivo.
Devuelve un objeto JSON con {"rows": [...], "omitted": [...]}.
Cada fila: {"kind": null, "amount_usd": null, "at": null, "status": null}.
- kind: "deposito" para depósitos/abonos que entraron a Hapi, "retiro" para
  retiros hacia el banco, "dividendo" para dividendos cobrados.
- amount_usd: importe en dólares exactamente como figura, positivo incluso en
  retiros. Si el movimiento figura en soles, deja amount_usd en null: no
  conviertas monedas. Copia números sin cálculos ni redondeos.
- at: fecha ISO YYYY-MM-DD solo si se ve con certeza; null en caso contrario.
  Nunca uses hoy ni la fecha de la captura.
- status: el estado del movimiento exactamente como figura ("Terminado",
  "Creado", "Cancelado", "Expirado", etc.); null si no se ve.
- Usa null en todo campo no visible, ilegible o dudoso; nunca inventes,
  estimes ni completes valores. Cada movimiento visible que no puedas
  clasificar debe aparecer en omitted con su motivo; no lo ocultes.
- Si no se ven movimientos, devuelve {"rows": [], "omitted": []}.
Responde solo JSON válido, sin markdown ni texto adicional."""

CONTRIB_KINDS = {"deposito", "retiro", "dividendo", "ahorro_soles"}
KINDS = CONTRIB_KINDS | {"actividad", "w8ben"}
SOURCES = {"captura", "texto", "historial"}
DONE = {"terminado", "completado", "completed"}
_KIND_ALIASES = {"deposit": "deposito", "abono": "deposito",
                 "withdrawal": "retiro", "dividend": "dividendo"}

_NUM = r"(\d+(?:[.,]\d+)?)"
_FECHA = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})"


class FlowSyncError(Exception):
    """Movimiento inválido o fallo de configuración/red del proveedor de IA."""


def _fold(text):
    """Minúsculas sin acentos: «Deposité» y «deposite» deben ser lo mismo."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower())
                   if not unicodedata.combining(c))


def _fecha_iso(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def _fecha_token(token):
    """ISO o D/M/YYYY → ISO; nada inválido pasa."""
    token = str(token).strip()
    try:
        if "/" in token:
            d, m, y = (int(p) for p in token.split("/"))
            return date(y, m, d).isoformat()
        return date.fromisoformat(token).isoformat()
    except ValueError:
        return None


def _money(value, field, required=True):
    if value is None or isinstance(value, bool):
        if required:
            raise FlowSyncError(f"{field}: número inválido o ausente")
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        if required:
            raise FlowSyncError(f"{field}: número inválido o ausente") from None
        return None
    if not math.isfinite(n) or n <= 0:
        if required:
            raise FlowSyncError(f"{field}: debe ser un número positivo finito")
        return None
    return n


def _canonical_amount(value):
    """221.5 y 221.50 son el mismo movimiento: forma canónica sin ceros."""
    if value is None:
        return ""
    d = Decimal(str(value))
    return format(d.normalize(), "f") if d else "0"


def fingerprint(row):
    """kind | día | coalesce(amount_usd, soles_amount), sin `source`: el mismo
    movimiento por captura o por texto choca aquí; dos ahorros distintos del
    mismo día (S/80 y S/120) no. Sirve para detectar duplicados, no bloquear."""
    amount = row.get("amount_usd")
    if amount is None:
        amount = row.get("soles_amount")
    return f"{row.get('kind')}|{(row.get('at') or '')[:10]}|{_canonical_amount(amount)}"


def _status_done(status):
    return _fold(status or "").strip() in DONE


def parse_message(text, today):
    """Conversación determinista → filas de borrador. [] si nada coincide."""
    t = _fold(text)
    hoy = _fecha_iso(today) or date.today().isoformat()
    rows = []
    # W-8BEN: la fecha del mensaje es la de vencimiento, no la del registro.
    if re.search(r"w\s*-?\s*8\s*-?\s*ben", t):
        m = re.search(r"vence\s+(?:el\s+)?" + _FECHA, t)
        expiry = _fecha_token(m.group(1)) if m else None
        if expiry:
            rows.append({"kind": "w8ben", "at": expiry})
    explicit = re.search(r"(?:\bel\s+" + _FECHA + r"|\b" + _FECHA + r"\b)", t)
    at = _fecha_token(explicit.group(1) or explicit.group(2)) if explicit else None
    at = at or hoy
    if re.search(r"\b(?:entre|ingrese|abri|me meti|inicie sesion|me loguee)\b"
                 r"[^.\n]{0,20}?\bhapi\b", t):
        rows.append({"kind": "actividad", "at": at})
    m = re.search(r"\bdeposite\s*(s/|\$)?\s*" + _NUM + r"\s*(soles|dolares?|usd)?\b", t)
    if m:
        marker, amount, unit = m.group(1), float(m.group(2).replace(",", ".")), m.group(3)
        row = {"kind": "deposito", "at": at, "source": "texto"}
        if marker == "$" or unit in ("dolares", "dolar", "usd"):
            row["amount_usd"] = amount
        else:  # depósito bancario peruano: sin marca de USD son soles
            row["soles_amount"] = amount
        llego = re.search(r"\blleg(?:aron|o|ue)\b\s*\$?\s*" + _NUM, t)
        if llego:
            usd = float(llego.group(1).replace(",", "."))
            row["amount_usd"] = usd
            if row.get("soles_amount"):
                # tc implícito del propio depósito: solo se guarda como dato
                row["fx_rate"] = round(row["soles_amount"] / usd, 4)
        rows.append(row)
    m = re.search(r"\b(?:retire|saque)\b\s*(s/|\$)?\s*" + _NUM
                  + r"\s*(soles|dolares?|usd)?\b", t)
    if m:
        row = {"kind": "retiro", "at": at, "source": "texto"}
        amount = float(m.group(2).replace(",", "."))
        if m.group(1) == "s/" or m.group(3) == "soles":
            row["soles_amount"] = amount
        else:
            row["amount_usd"] = amount
        rows.append(row)
    m = re.search(r"\b(?:guarde|ahorre)\b\s*(?:s/\s*)?" + _NUM + r"\s*(?:soles)?\b", t)
    if m:
        rows.append({"kind": "ahorro_soles",
                     "soles_amount": float(m.group(1).replace(",", ".")),
                     "at": at, "source": "texto"})
    m = re.search(r"\bdividendos?\b[^.\n]{0,30}?(s/|\$)?\s*" + _NUM
                  + r"\s*(soles|dolares?|usd)?\b", t)
    if m:
        row = {"kind": "dividendo", "at": at, "source": "texto"}
        amount = float(m.group(2).replace(",", "."))
        if m.group(1) == "s/" or m.group(3) == "soles":
            row["soles_amount"] = amount
        else:
            row["amount_usd"] = amount
        rows.append(row)
    return rows


def normalize_movement(raw):
    """Valida un movimiento extraído del historial; solo campos visibles."""
    if not isinstance(raw, dict):
        raise FlowSyncError("fila no reconocida")
    kind = _fold(raw.get("kind") or "").strip()
    kind = _KIND_ALIASES.get(kind, kind)
    if kind not in ("deposito", "retiro", "dividendo"):
        raise FlowSyncError("kind: debe ser deposito, retiro o dividendo")
    amount = _money(raw.get("amount_usd"), "amount_usd")
    at = _fecha_iso(raw.get("at"))
    if at is None:
        raise FlowSyncError("at: fecha ISO inválida o ausente")
    return {"kind": kind, "amount_usd": amount, "at": at}


def normalize_row(raw):
    """Valida una fila confirmada por el usuario (texto, captura o historial).

    actividad y w8ben no son movimientos de dinero: actualizan ajustes y no se
    guardan en contributions."""
    if not isinstance(raw, dict):
        raise FlowSyncError("fila no reconocida")
    kind = _fold(raw.get("kind") or "").strip()
    kind = _KIND_ALIASES.get(kind, kind)
    if kind not in KINDS:
        raise FlowSyncError("kind no reconocido")
    at = _fecha_iso(raw.get("at"))
    if at is None:
        raise FlowSyncError("at: fecha ISO inválida o ausente")
    if kind not in CONTRIB_KINDS:
        return {"kind": kind, "at": at}
    source = _fold(raw.get("source") or "texto").strip()
    if source not in SOURCES:
        raise FlowSyncError("source: debe ser captura, texto o historial")
    usd = _money(raw.get("amount_usd"), "amount_usd",
                 required=kind in ("retiro", "dividendo"))
    soles = _money(raw.get("soles_amount"), "soles_amount",
                   required=kind == "ahorro_soles")
    if kind == "deposito" and usd is None and soles is None:
        raise FlowSyncError("deposito: hace falta el monto en USD o en soles")
    row = {"kind": kind, "amount_usd": usd, "soles_amount": soles,
           "fx_rate": _money(raw.get("fx_rate"), "fx_rate", required=False),
           "at": at, "source": source}
    row["fingerprint"] = fingerprint(row)
    return row


def _movements(reply, source, model):
    if (not isinstance(reply, dict) or not isinstance(reply.get("rows"), list)
            or not isinstance(reply.get("omitted"), list)):
        raise FlowSyncError("La IA no devolvió listas de rows y omitted")
    rows, omitted = [], list(reply["omitted"])
    for raw in reply["rows"]:
        try:
            if not isinstance(raw, dict):
                raise FlowSyncError("fila no reconocida")
            if not _status_done(raw.get("status")):
                raise FlowSyncError(f"estado {raw.get('status')!r}: solo entra «Terminado»")
            rows.append({**normalize_movement(raw), "source": source})
        except FlowSyncError as exc:
            omitted.append({"fila": raw, "motivo": str(exc)})
    return {"rows": rows, "omitted": omitted, "model": model}


def analyze_image(image_b64, mime, env=None, client=None):
    """Captura de la app de Hapi → movimientos para revisar; no guarda nada."""
    try:
        reply, model = AP.request(PROMPT, "Extrae únicamente los movimientos de dinero visibles.",
                                  image_b64=image_b64, mime=mime, env=env, client=client,
                                  json_reply=True)
    except AP.AIProviderError as exc:
        raise FlowSyncError(str(exc)) from exc
    return _movements(reply, "captura", model)


def analyze_text(text, env=None, client=None):
    """Historial de movimientos pegado como texto → filas para revisar."""
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise FlowSyncError("Pega el historial de movimientos de Hapi")
    try:
        reply, model = AP.request(PROMPT,
                                  "Historial de Hapi pegado por el usuario:\n" + text.strip(),
                                  env=env, client=client, json_reply=True)
    except AP.AIProviderError as exc:
        raise FlowSyncError(str(exc)) from exc
    return _movements(reply, "historial", model)
