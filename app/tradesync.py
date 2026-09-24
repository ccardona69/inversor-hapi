"""Extracción y cálculo de operaciones Hapi, sin escrituras ni operaciones de bróker.

Los importes internos son Decimal. Para JSON, el preview devuelve números como
cadenas decimales exactas; no los conviertas a float antes de revisarlos.
"""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext

from . import ai_provider as AP


PROMPT = """Eres Luna, extractor estricto de órdenes ejecutadas de Hapi. Lee solo
operaciones de compra o venta que se ven en esta captura; no confundas órdenes
pendientes, resúmenes de cartera ni cotizaciones con operaciones ejecutadas.
Devuelve un objeto JSON con {"rows": [...], "omitted": [...]}.
Cada fila: {"ticker": null, "side": null, "qty": null, "price": null,
"fees": null, "at": null, "currency": null, "order_id": null}.
- Transcribe ticker, lado, cantidad de acciones, precio por acción y comisión
  exactamente como figuran. Nunca inventes, estimes, redondees, calcules costos,
  deduzcas la comisión de totales ni pongas fees=0 si no está visible.
- Pon currency="USD" SOLO si la moneda USD se ve explícitamente en la orden;
  si no, null. No conviertas monedas. Conserva order_id SOLO si se ve.
- En at usa fecha ISO YYYY-MM-DD; agrega T y hora/minutos/segundos y zona
  SOLO si se ven con certeza. Si no se ve fecha, null; nunca uses hoy ni la
  fecha de la captura. No inventes horas ni orden cronológico.
- Usa null en todo campo no visible, ilegible o dudoso. Cada operación visible
  que no puedas identificar como compra/venta con ticker, qty y price debe
  aparecer en omitted con su motivo; no la ocultes ni completes valores.
- Copia números sin cálculos; si la captura no muestra operaciones, rows=[];
  explica en omitted cualquier operación omitida.
Responde solo JSON válido, sin markdown ni texto adicional."""

TICKER = re.compile(r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?\Z")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ISO_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?\Z"
)
SIDES = {"comprar": "comprar", "compra": "comprar", "buy": "comprar",
         "vender": "vender", "venta": "vender", "sell": "vender"}


class TradeSyncError(ValueError):
    """Dato de operación ausente, ambiguo o inválido."""


def _decimal(value, field, *, nullable=False, zero_ok=False):
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise TradeSyncError(f"{field}: número inválido o ausente")
    if isinstance(value, str) and not value.strip():
        raise TradeSyncError(f"{field}: número inválido o ausente")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise TradeSyncError(f"{field}: número inválido") from exc
    if (not number.is_finite() or number < 0 or (not zero_ok and number == 0)
            or (number != 0 and abs(number.adjusted()) > 308)):
        raise TradeSyncError(f"{field}: número no finito o fuera de rango")
    return number


def _at(value):
    if value is None:
        return None
    if not isinstance(value, str) or not (ISO_DATE.fullmatch(value) or ISO_DATETIME.fullmatch(value)):
        raise TradeSyncError("at: fecha ISO inválida")
    try:
        if ISO_DATE.fullmatch(value):
            date.fromisoformat(value)
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TradeSyncError("at: fecha ISO inválida") from exc
    return value


def normalize_trade(row, require_complete=False):
    """Valida solo campos de una orden visible; preview permite fees/at/moneda null.

    Devuelve qty, price y fees como Decimal (sin precisión flotante adicional).
    require_complete exige comisión observada (incluido cero explícito), fecha
    y USD explícito; nunca rellena valores desde el esquema de SQLite.
    """
    if not isinstance(row, dict):
        raise TradeSyncError("fila no reconocida")
    ticker = row.get("ticker")
    if not isinstance(ticker, str) or not TICKER.fullmatch(ticker.strip().upper()):
        raise TradeSyncError("ticker: símbolo inválido o ausente")
    side = row.get("side")
    if not isinstance(side, str) or side.strip().lower() not in SIDES:
        raise TradeSyncError("side: compra o venta no identificada")
    currency = row.get("currency")
    if currency is not None:
        if not isinstance(currency, str) or currency.strip().upper() != "USD":
            raise TradeSyncError("currency: solo se admiten órdenes en USD")
        currency = "USD"
    at = _at(row.get("at"))
    fees = _decimal(row.get("fees"), "fees", nullable=True, zero_ok=True)
    if require_complete and (at is None or fees is None or currency is None):
        raise TradeSyncError("Faltan fecha, comisión visible o moneda USD explícita")
    order_id = row.get("order_id")
    if order_id is not None:
        if not isinstance(order_id, (str, int)) or isinstance(order_id, bool) or not str(order_id).strip():
            raise TradeSyncError("order_id: identificador inválido")
        order_id = str(order_id).strip()
    result = {
        "ticker": ticker.strip().upper(), "side": SIDES[side.strip().lower()],
        "qty": _decimal(row.get("qty"), "qty"),
        "price": _decimal(row.get("price"), "price"),
        "fees": fees, "at": at, "currency": currency,
    }
    if order_id is not None:
        result["order_id"] = order_id
    return result


def analyze(image_b64, mime, env=None, client=None):
    """Propone órdenes para revisión; filas incompletas conservan null, sin guardar."""
    try:
        reply, model = AP.request(PROMPT, "Extrae únicamente las órdenes Hapi visibles.",
                                  image_b64=image_b64, mime=mime, env=env, client=client,
                                  json_reply=True)
    except AP.AIProviderError as exc:
        raise TradeSyncError(str(exc)) from exc
    if not isinstance(reply, dict) or not isinstance(reply.get("rows"), list) or not isinstance(reply.get("omitted"), list):
        raise TradeSyncError("La IA no devolvió listas de rows y omitted")
    rows, omitted = [], list(reply["omitted"])
    for raw in reply["rows"]:
        try:
            row = normalize_trade(raw)
        except TradeSyncError as exc:
            omitted.append({"fila": raw, "motivo": str(exc)})
            continue
        rows.append({key: str(value) if isinstance(value, Decimal) else value
                     for key, value in row.items()})
    return {"rows": rows, "omitted": omitted, "model": model}


def _sorted_trades(trades):
    if not isinstance(trades, (list, tuple)) or not trades:
        raise TradeSyncError("Se requieren operaciones para calcular el costo")
    rows = [normalize_trade(row, require_complete=True) for row in trades]
    if len({row["ticker"] for row in rows}) != 1:
        raise TradeSyncError("Calcula el costo de un ticker a la vez")
    dates = {}
    instants = {}
    kinds = set()
    for row in rows:
        at = row["at"]
        day = at[:10]
        date_only = len(at) == 10
        dates.setdefault(day, {"sides": set(), "without_time": False})
        group = dates[day]
        group["sides"].add(row["side"])
        group["without_time"] |= date_only
        if not date_only:
            parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
            kind = "aware" if parsed.tzinfo is not None else "naive"
            kinds.add(kind)
            instant = parsed.astimezone(timezone.utc) if kind == "aware" else parsed
            instants.setdefault(instant, set()).add(row["side"])
    if len(kinds) > 1 or ("aware" in kinds and any(group["without_time"] for group in dates.values())):
        raise TradeSyncError("No se puede ordenar fechas con zonas horarias desconocidas")
    for group in dates.values():
        if group["without_time"] and len(group["sides"]) > 1:
            raise TradeSyncError("Orden ambiguo: compras y ventas sin hora el mismo día")
    if any(len(sides) > 1 for sides in instants.values()):
        raise TradeSyncError("Orden ambiguo: compra y venta a la misma hora")

    def sort_key(row):
        at = row["at"]
        if len(at) == 10:
            return (at, datetime.min)
        parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
        return (at[:10], parsed)

    # Para instantes con zona, ordenar globalmente en UTC, no por día local.
    if "aware" in kinds:
        rows.sort(key=lambda row: datetime.fromisoformat(row["at"].replace("Z", "+00:00")).astimezone(timezone.utc))
    else:
        rows.sort(key=sort_key)
    return rows


def cost_basis(trades):
    """Costo promedio ponderado en USD de UN ticker, sin redondear ni persistir.

    Compras suman qty*price+fees; ventas restan qty*promedio previo.
    La comisión de venta afecta el resultado realizado, NO el costo remanente.
    Exige historial completo desde cero; no asume posiciones anteriores.
    Devuelve qty, invested y avg_cost como Decimal (serializar a str para JSON).
    """
    rows = _sorted_trades(trades)
    with localcontext() as ctx:
        ctx.prec = 50
        qty, invested = Decimal(0), Decimal(0)
        for row in rows:
            amount = row["qty"]
            if row["side"] == "comprar":
                invested += amount * row["price"] + row["fees"]
                qty += amount
            else:
                if amount > qty:
                    raise TradeSyncError("Venta mayor a las acciones disponibles")
                if amount == qty:
                    qty, invested = Decimal(0), Decimal(0)
                else:
                    invested -= invested * amount / qty
                    qty -= amount
        return {"qty": +qty, "invested": +invested,
                "avg_cost": +(invested / qty) if qty else Decimal(0)}


def trade_fingerprint(row):
    """Huella de campos visibles completos, NO prueba única de identidad.

    Sin order_id, dos órdenes genuinas iguales podrían tener la misma huella:
    úsala para detectar candidatos a duplicado, no para descartar automáticamente.
    Incluye la fecha/hora tal como se vio; no agrega segundos ni defaults.
    """
    normalized = normalize_trade(row, require_complete=True)

    def canonical(value):
        if not isinstance(value, Decimal):
            return value
        if value == 0:
            return "0"
        text = format(value, "f")  # Decimal.normalize() redondearía con la precisión del contexto.
        return text.rstrip("0").rstrip(".") if "." in text else text

    fields = {key: canonical(value) for key, value in normalized.items()}
    payload = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
