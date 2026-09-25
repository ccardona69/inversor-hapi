"""Fundamentales oficiales desde SEC EDGAR (companyfacts). Solo lectura pública,
sin clave; nunca estima ni mezcla presentaciones: lo que el 10-K no dice, falta."""
import os
from datetime import date

import httpx

from .analysis import FUND_FIELDS, TEXT_FUND_FIELDS

SEC_UA_DEFAULT = "InversorHapiIA/1.0 (uso personal local)"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

_TICKER_CACHE = {}

# company_tickers.json omite a algunas emisoras que sí presentan 10-K:
# "XOM" apunta ahí a "ExxonMobil Holdings Corp" (CIK 2115436, vehículo sin
# 10-K), mientras la operadora real es "Exxon Mobil Corporation" (CIK 34088).
# Verificado en data.sec.gov. Se puede extender si aparece otro caso.
CIK_OVERRIDES = {"XOM": 34088}

REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
COST_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold"]
DDA_TAGS = ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet", "Depreciation"]
ST_INV_TAGS = ["ShortTermInvestments", "MarketableSecuritiesCurrent",
               "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
               "AvailableForSaleSecuritiesDebtSecurities"]


class SecDataError(Exception):
    """Error de consulta o de datos de la SEC con un código HTTP sugerido."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _clear_cache():
    """Para pruebas: vacía la caché de tickers de la SEC."""
    _TICKER_CACHE.clear()


def _get(url, client):
    headers = {"User-Agent": os.environ.get("INVERSOR_SEC_USER_AGENT") or SEC_UA_DEFAULT}
    try:
        if client is None:
            with httpx.Client(timeout=30, headers=headers) as http:
                return http.get(url)
        return client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise SecDataError(502, "No se pudo consultar la SEC; inténtalo más tarde.") from exc


_UNREADABLE = "La SEC devolvió datos que no se pudieron leer."


def cik_for(ticker, client=None):
    """CIK numérico del ticker según la tabla oficial; sin entrada → 404."""
    tk = ticker.upper().strip().replace(".", "-")
    if tk in CIK_OVERRIDES:
        return CIK_OVERRIDES[tk]
    if "map" not in _TICKER_CACHE:
        r = _get(TICKERS_URL, client)
        if r.status_code != 200:
            raise SecDataError(502, "No se pudo consultar la SEC; inténtalo más tarde.")
        try:
            _TICKER_CACHE["map"] = {str(v["ticker"]).upper(): int(v["cik_str"])
                                    for v in r.json().values()}
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise SecDataError(502, _UNREADABLE) from exc
    cik = _TICKER_CACHE["map"].get(tk)
    if cik is None:
        raise SecDataError(404, f"No hay datos de empresa en la SEC para {tk}: "
                                "los ETF y fondos no presentan 10-K.")
    return cik


def _d(s):
    return date.fromisoformat(str(s)[:10])


def extract_fundamentals(facts: dict) -> dict:
    """Función pura: del JSON de companyfacts saca los fundamentales del último 10-K.

    Solo hechos del mismo filing (accn), anual = duración de 350–380 días,
    instantáneo = sin 'start' y end == cierre del ejercicio. Nunca mezcla
    presentaciones ni estima valores."""
    try:
        g = facts["facts"]["us-gaap"]
    except KeyError as exc:
        raise SecDataError(404, "La SEC no tiene un 10-K para esta empresa.") from exc
    best = None
    for tag in g.values():
        for unit_facts in (tag.get("units") or {}).values():
            for h in unit_facts:
                if h.get("form") == "10-K":
                    key = (h.get("filed") or "", h.get("accn") or "")
                    if best is None or key > best:
                        best = key
    if best is None:
        raise SecDataError(404, "La SEC no tiene un 10-K para esta empresa.")
    filed, accn = best

    def annual(tag, unit):
        out = []
        for h in (g.get(tag) or {}).get("units", {}).get(unit, []):
            if h.get("accn") != accn or "start" not in h:
                continue
            days = (_d(h["end"]) - _d(h["start"])).days
            if 350 <= days <= 380:
                out.append(h)
        return out

    def annual_actual_prev(tag, unit):
        """(actual, previo): el mayor end anual; el previo a ~1 año del actual."""
        vals = annual(tag, unit)
        if not vals:
            return None, None
        actual = max(vals, key=lambda h: h["end"])
        prevs = [h for h in vals
                 if 350 <= (_d(actual["end"]) - _d(h["end"])).days <= 380]
        previo = max(prevs, key=lambda h: h["end"]) if prevs else None
        return actual, previo

    # Cierre del ejercicio: el de los ingresos; sin ingresos, el mayor de NetIncomeLoss.
    fy_end = None
    for tag in REVENUE_TAGS:
        actual, _ = annual_actual_prev(tag, "USD")
        if actual is not None:
            fy_end = actual["end"]
            break
    if fy_end is None:
        vals = annual("NetIncomeLoss", "USD")
        if not vals:
            raise SecDataError(404, "El 10-K no trae un estado de resultados anual reconocible.")
        fy_end = max(vals, key=lambda h: h["end"])["end"]

    def year_pair(tag, unit):
        """(actual, previo) solo si el mayor end coincide con el cierre del ejercicio."""
        actual, previo = annual_actual_prev(tag, unit)
        if actual is None or actual["end"] != fy_end:
            return None, None
        return actual["val"], (previo["val"] if previo else None)

    def instant(tag, unit):
        for h in (g.get(tag) or {}).get("units", {}).get(unit, []):
            if h.get("accn") == accn and "start" not in h and h.get("end") == fy_end:
                return h["val"]
        return None

    data, detalle = {}, {}

    for tag in REVENUE_TAGS:
        actual, previo = year_pair(tag, "USD")
        if actual is not None:
            data["revenue"] = actual
            detalle["revenue"] = tag
            if previo is not None and previo > 0:
                data["revenue_growth_pct"] = round((actual / previo - 1) * 100, 2)
            break

    eps, eps_prev = year_pair("EarningsPerShareDiluted", "USD/shares")
    if eps is not None:
        data["eps"] = eps
        detalle["eps"] = "EarningsPerShareDiluted"
        if eps_prev is not None and eps_prev > 0:
            data["eps_growth_pct"] = round((eps / eps_prev - 1) * 100, 2)

    shares, _ = year_pair("WeightedAverageNumberOfDilutedSharesOutstanding", "shares")
    if shares is not None:
        data["shares_out"] = shares
        detalle["shares_out"] = "WeightedAverageNumberOfDilutedSharesOutstanding"

    op_cf, _ = year_pair("NetCashProvidedByUsedInOperatingActivities", "USD")
    capex, capex_tag = None, None
    for tag in CAPEX_TAGS:
        capex, _ = year_pair(tag, "USD")
        if capex is not None:
            capex_tag = tag
            break
    if op_cf is not None and capex is not None:
        data["fcf"] = op_cf - capex
        detalle["fcf"] = f"NetCashProvidedByUsedInOperatingActivities − {capex_tag}"

    op_inc, _ = year_pair("OperatingIncomeLoss", "USD")
    if op_inc is not None and "revenue" in data:
        data["op_margin_pct"] = round(op_inc / data["revenue"] * 100, 2)
        detalle["op_margin_pct"] = "OperatingIncomeLoss / ingresos"

    gross, _ = year_pair("GrossProfit", "USD")
    if gross is None and "revenue" in data:
        for tag in COST_TAGS:
            cost, _ = year_pair(tag, "USD")
            if cost is not None:
                gross = data["revenue"] - cost
                detalle["gross_margin_pct"] = f"ingresos − {tag}"
                break
    if gross is not None and "revenue" in data:
        data["gross_margin_pct"] = round(gross / data["revenue"] * 100, 2)
        detalle.setdefault("gross_margin_pct", "GrossProfit / ingresos")

    dda, dda_tag = None, None
    for tag in DDA_TAGS:
        dda, _ = year_pair(tag, "USD")
        if dda is not None:
            dda_tag = tag
            break
    if op_inc is not None and dda is not None:
        data["ebitda"] = op_inc + dda
        detalle["ebitda"] = f"OperatingIncomeLoss + {dda_tag}"

    buybacks, _ = year_pair("PaymentsForRepurchaseOfCommonStock", "USD")
    if buybacks is not None:
        data["buybacks"] = buybacks
        detalle["buybacks"] = "PaymentsForRepurchaseOfCommonStock"

    cash = instant("CashCashEquivalentsAndShortTermInvestments", "USD")
    if cash is not None:
        data["cash"] = cash
        detalle["cash"] = "CashCashEquivalentsAndShortTermInvestments"
    else:
        cash_eq = instant("CashAndCashEquivalentsAtCarryingValue", "USD")
        if cash_eq is not None:
            st_tag = next((t for t in ST_INV_TAGS if instant(t, "USD") is not None), None)
            st_inv = instant(st_tag, "USD") if st_tag else 0
            data["cash"] = cash_eq + st_inv
            detalle["cash"] = ("CashAndCashEquivalentsAtCarryingValue + " + st_tag
                               if st_tag else
                               "CashAndCashEquivalentsAtCarryingValue (sin inversiones corto plazo reportadas)")

    ltd, ltd_note = None, None
    v = instant("LongTermDebt", "USD")
    if v is not None:
        ltd, ltd_note = v, "LongTermDebt"
    else:
        v = instant("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities", "USD")
        if v is not None:
            ltd, ltd_note = v, "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"
        else:
            nc = instant("LongTermDebtNoncurrent", "USD")
            if nc is not None:
                ltd = nc + (instant("LongTermDebtCurrent", "USD") or 0)
                ltd_note = "LongTermDebtNoncurrent + LongTermDebtCurrent"
            else:
                nc = instant("LongTermDebtAndCapitalLeaseObligations", "USD")
                if nc is not None:
                    ltd = nc + (instant("LongTermDebtAndCapitalLeaseObligationsCurrent", "USD") or 0)
                    ltd_note = ("LongTermDebtAndCapitalLeaseObligations"
                                " + LongTermDebtAndCapitalLeaseObligationsCurrent")
    if ltd is not None:
        extras = [t for t in ("CommercialPaper", "ShortTermBorrowings", "OtherShortTermBorrowings")
                  if instant(t, "USD") is not None]
        data["debt"] = ltd + sum(instant(t, "USD") for t in extras)
        detalle["debt"] = " + ".join([ltd_note] + extras) if extras else ltd_note

    numeric = [k for k, _ in FUND_FIELDS if k not in TEXT_FUND_FIELDS]
    missing = [label for k, label in FUND_FIELDS if k in numeric and k not in data]
    return {"data": data, "period_end": fy_end, "filed": filed, "accn": accn,
            "missing": missing, "detalle": detalle}


def fetch_fundamentals(ticker, client=None):
    """Ticker → companyfacts del último 10-K → fundamentales (ver extract)."""
    cik = cik_for(ticker, client)
    r = _get(FACTS_URL.format(cik=cik), client)
    if r.status_code == 404:
        raise SecDataError(404, "La SEC no tiene un 10-K para esta empresa.")
    if r.status_code != 200:
        raise SecDataError(502, "No se pudo consultar la SEC; inténtalo más tarde.")
    try:
        facts = r.json()
        return extract_fundamentals(facts)
    except SecDataError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SecDataError(502, _UNREADABLE) from exc
