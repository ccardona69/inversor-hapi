"""Extracción y costo de órdenes Hapi: pruebas puras, sin red ni SQLite."""
from decimal import Decimal

import pytest

from app import ai_provider as AP
from app import tradesync as TS


def trade(**changes):
    return {"ticker": "voo", "side": "buy", "qty": "1.25", "price": "100.10",
            "fees": "0.25", "currency": "USD", "at": "2026-01-01", **changes}


def test_analyze_uses_provider_and_preserves_unknowns(monkeypatch):
    calls = []

    def fake_request(instructions, user_text, **kwargs):
        calls.append((instructions, user_text, kwargs))
        return {"rows": [trade(fees=None, at=None, currency=None,
                               order_id="ord-1", extra="ignorar"),
                         trade(qty=None), {"ticker": "VTI", "side": "sell",
                                            "qty": 2, "price": 10, "fees": None}],
                "omitted": [{"motivo": "orden ilegible"}]}, "luna-prueba"

    monkeypatch.setattr(AP, "request", fake_request)
    result = TS.analyze("imagen", "image/png", env={"test": "yes"}, client=object())
    assert result == {"rows": [{"ticker": "VOO", "side": "comprar", "qty": "1.25",
                               "price": "100.10", "fees": None, "at": None,
                               "currency": None, "order_id": "ord-1"},
                              {"ticker": "VTI", "side": "vender", "qty": "2",
                               "price": "10", "fees": None, "at": None, "currency": None}],
                      "omitted": [{"motivo": "orden ilegible"},
                                  {"fila": trade(qty=None),
                                   "motivo": "qty: número inválido o ausente"}],
                      "model": "luna-prueba"}
    assert "Nunca inventes" in calls[0][0] and "fees=0" in calls[0][0]
    assert "fecha" in calls[0][0] and "omitted" in calls[0][0]
    assert calls[0][2] == {"image_b64": "imagen", "mime": "image/png",
                           "env": {"test": "yes"}, "client": calls[0][2]["client"],
                           "json_reply": True}


def test_analyze_rejects_bad_provider_reply(monkeypatch):
    monkeypatch.setattr(AP, "request", lambda *a, **kw: ({"rows": None, "omitted": []}, "luna"))
    with pytest.raises(TS.TradeSyncError, match="listas"):
        TS.analyze("x", "image/png")

    def fail(*a, **kw):
        raise AP.AIProviderError("no configurada")

    monkeypatch.setattr(AP, "request", fail)
    with pytest.raises(TS.TradeSyncError, match="no configurada"):
        TS.analyze("x", "image/png")


def test_normalize_only_visible_fields_and_required_values():
    row = TS.normalize_trade(trade(side="Compra", fees=None, at=None, currency=None,
                                   estimated_total=400))
    assert row == {"ticker": "VOO", "side": "comprar", "qty": Decimal("1.25"),
                   "price": Decimal("100.10"), "fees": None, "at": None,
                   "currency": None}
    with pytest.raises(TS.TradeSyncError, match="Faltan"):
        TS.normalize_trade(row, require_complete=True)
    assert TS.normalize_trade(trade(fees=0), require_complete=True)["fees"] == 0
    assert TS.normalize_trade(trade(side="venta"))["side"] == "vender"


@pytest.mark.parametrize("changes", [
    {"ticker": "VOO; DROP TABLE trades"}, {"ticker": "../VOO"}, {"side": "hold"},
    {"qty": None}, {"qty": 0}, {"qty": "NaN"}, {"qty": "1e999999"},
    {"price": -1}, {"price": float("inf")}, {"price": True},
    {"fees": -1}, {"fees": "NaN"}, {"currency": "EUR"},
    {"at": "2026-02-30"}, {"at": "mañana"}, {"at": "2026-01-01T25:00"},
    {"at": "2026-01-01 12:00"}, {"order_id": ""},
])
def test_normalize_rejects_invalid_values(changes):
    with pytest.raises(TS.TradeSyncError):
        TS.normalize_trade(trade(**changes))


@pytest.mark.parametrize("changes", [{"fees": None}, {"at": None}, {"currency": None}])
def test_cost_basis_requires_every_visible_field(changes):
    with pytest.raises(TS.TradeSyncError):
        TS.cost_basis([trade(**changes)])
    with pytest.raises(TS.TradeSyncError):
        TS.trade_fingerprint(trade(**changes))


def test_cost_basis_weighted_fractional_buy_sell_and_fees():
    rows = [trade(side="vender", qty="0.5", price="150", fees="7", at="2026-01-03"),
            trade(qty="1.25", price="100", fees="0.25", at="2026-01-01"),
            trade(qty="0.75", price="200", fees="0.75", at="2026-01-02")]
    result = TS.cost_basis(rows)
    assert result == {"qty": Decimal("1.5"), "invested": Decimal("207"),
                      "avg_cost": Decimal("138")}
    assert TS.cost_basis([*rows, trade(side="sell", qty="1.5", price="1", fees=8,
                                        at="2026-01-04")]) == {
        "qty": Decimal(0), "invested": Decimal(0), "avg_cost": Decimal(0)}


def test_identical_orders_are_not_silently_deduplicated():
    duplicate = trade()
    assert TS.trade_fingerprint(duplicate) == TS.trade_fingerprint(dict(duplicate))
    assert TS.cost_basis([duplicate, dict(duplicate)]) == {
        "qty": Decimal("2.50"), "invested": Decimal("250.750"),
        "avg_cost": Decimal("100.3")}


def test_cost_basis_rejects_oversell_and_multiple_tickers():
    with pytest.raises(TS.TradeSyncError, match="Venta mayor"):
        TS.cost_basis([trade(side="sell", qty="2")])
    with pytest.raises(TS.TradeSyncError, match="ticker"):
        TS.cost_basis([trade(), trade(ticker="VTI", at="2026-01-02")])
    with pytest.raises(TS.TradeSyncError, match="operaciones"):
        TS.cost_basis([])


@pytest.mark.parametrize("buy_at,sell_at", [
    ("2026-01-01", "2026-01-01"),
    ("2026-01-01", "2026-01-01T16:00"),
    ("2026-01-01T10:00", "2026-01-01T10:00"),
    ("2026-01-01T11:00Z", "2026-01-01T12:00+01:00"),
    ("2026-01-01T23:00Z", "2026-01-02T00:00+01:00"),
])
def test_cost_basis_rejects_ambiguous_order(buy_at, sell_at):
    with pytest.raises(TS.TradeSyncError, match="ambiguo"):
        TS.cost_basis([trade(at=buy_at), trade(side="sell", at=sell_at)])


def test_cost_basis_rejects_unknown_timezone_and_accepts_explicit_sequence():
    with pytest.raises(TS.TradeSyncError, match="zonas horarias"):
        TS.cost_basis([trade(at="2026-01-01T10:00Z"),
                       trade(side="sell", at="2026-01-02T10:00")])
    assert TS.cost_basis([trade(side="sell", at="2026-01-01T11:00Z"),
                          trade(at="2026-01-01T10:00Z")])["qty"] == 0


def test_fingerprint_stable_and_differentiates_visible_fields():
    original = trade(order_id="orden-A")
    fingerprint = TS.trade_fingerprint(original)
    assert fingerprint == TS.trade_fingerprint(trade(order_id="orden-A", qty="1.2500",
                                                   side="comprar", ticker="VOO"))
    assert fingerprint != TS.trade_fingerprint(trade(order_id="orden-B"))
    assert fingerprint != TS.trade_fingerprint(trade(order_id="orden-A", fees="0.26"))
    assert fingerprint != TS.trade_fingerprint(trade(order_id="orden-A", at="2026-01-02"))
    # Sin identificador, dos órdenes idénticas son candidatos, no duplicados comprobados.
    assert TS.trade_fingerprint(trade()) == TS.trade_fingerprint(trade())
    assert TS.trade_fingerprint(trade(qty="1.1234567890123456789012345678901")) != \
        TS.trade_fingerprint(trade(qty="1.1234567890123456789012345678902"))
