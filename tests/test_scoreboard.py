"""Marcador de bolsillo y fantasma SPY: cálculos puros, sin BD ni red."""
import pytest

from app import scoreboard as SB

# Historial real del usuario (aceptación): 9 depósitos Terminado.
DEPOSITOS = [
    {"kind": "deposito", "amount_usd": 9, "at": "2025-12-26"},
    {"kind": "deposito", "amount_usd": 76.71, "at": "2026-01-07"},
    {"kind": "deposito", "amount_usd": 72, "at": "2026-01-26"},
    {"kind": "deposito", "amount_usd": 105.44, "at": "2026-02-23"},
    {"kind": "deposito", "amount_usd": 85.76, "at": "2026-04-15"},
    {"kind": "deposito", "amount_usd": 13, "at": "2026-05-21"},
    {"kind": "deposito", "amount_usd": 301, "at": "2026-08-24"},
    {"kind": "deposito", "amount_usd": 221.50, "at": "2026-08-25"},
    {"kind": "deposito", "amount_usd": 65, "at": "2026-09-08"},
]


def test_etf_pct_sobre_exposicion_con_precio():
    pos = [{"ticker": "AMZN", "market_value": 60},
           {"ticker": "VOO", "market_value": 40},
           {"ticker": "SINPRECIO", "market_value": None}]
    assert SB.etf_pct(pos) == 40.0
    assert SB.etf_pct([{"ticker": "AMZN", "market_value": 100}]) == 0.0
    assert SB.etf_pct([{"ticker": "AMZN", "market_value": None}]) is None


def test_depositado_neto_excluye_ahorro_dividendos_y_suma_retiros():
    rows = DEPOSITOS + [
        {"kind": "ahorro_soles", "soles_amount": 80, "at": "2026-09-10"},
        {"kind": "dividendo", "amount_usd": 1.25, "at": "2026-09-11"},
        {"kind": "retiro", "amount_usd": 50, "at": "2026-09-12"},
    ]
    assert SB.depositado_neto(DEPOSITOS) == 949.41
    assert SB.depositado_neto(rows) == 899.41  # 949.41 − 50 de retiro


def test_marcador_nueve_depositos_reales():
    m = SB.marcador(DEPOSITOS, valor_actual=1022.77, deposit_fee=3.0)
    assert m["depositado_neto"] == 949.41
    assert m["n_depositos"] == 9
    assert m["costos_deposito"] == 27.0
    assert m["costos_etiqueta"] == "ESTIMACIÓN"
    assert m["puesto_bolsillo"] == 976.41
    assert m["resultado_real"] == 46.36
    assert m["resultado_pct"] == pytest.approx(4.75, abs=0.01)
    # Sin los costos de depósito el resultado sería otro: no se deben omitir.
    assert round(1022.77 - 949.41, 2) == 73.36 != m["resultado_real"]
    assert len(m["costos_detalle"]) == 9


def test_marcador_sin_valor_actual_dice_sin_dato():
    m = SB.marcador(DEPOSITOS, valor_actual=None, deposit_fee=3.0)
    assert m["resultado_real"] is None and m["resultado_pct"] is None
    assert m["puesto_bolsillo"] == 976.41


def test_costo_deposito_calculo_con_tc_del_dia():
    row = {"kind": "deposito", "soles_amount": 480, "amount_usd": 132.50}
    c = SB.costo_deposito(row, tc_ref=3.55, deposit_fee=3.0)
    assert c["etiqueta"] == "CÁLCULO"
    assert c["valor"] == pytest.approx(2.71, abs=0.005)  # 480/3.55 − 132.50


def test_costo_deposito_nunca_usa_tc_implicito():
    # soles+usd sin tc de mercado → ESTIMACIÓN con la tarifa, nunca 0.
    row = {"kind": "deposito", "soles_amount": 480, "amount_usd": 132.50}
    c = SB.costo_deposito(row, tc_ref=None, deposit_fee=3.0)
    assert c["etiqueta"] == "ESTIMACIÓN" and c["valor"] == 3.0
    m = SB.marcador([row], valor_actual=200, deposit_fee=3.0,
                    tc_lookup=lambda fecha: None)
    assert m["costos_detalle"][0]["etiqueta"] == "ESTIMACIÓN"
    assert m["costos_deposito"] == 3.0


def test_costo_deposito_mezcla_etiquetas():
    rows = DEPOSITOS[:1] + [
        {"kind": "deposito", "soles_amount": 480, "amount_usd": 132.50,
         "at": "2026-01-01"}]
    m = SB.marcador(rows, valor_actual=200, deposit_fee=3.0,
                    tc_lookup=lambda fecha: (3.55, "Yahoo Finance PEN=X", fecha))
    assert m["costos_etiqueta"] == "ESTIMACIÓN"  # un depósito sin soles → estimado
    todo_calculo = [dict(r, soles_amount=400) for r in DEPOSITOS[:1]]
    m2 = SB.marcador(todo_calculo, valor_actual=200, deposit_fee=3.0,
                     tc_lookup=lambda fecha: (3.55, "f", fecha))
    assert m2["costos_etiqueta"] == "CÁLCULO"


def test_normalize_tc_acepta_ambos_sentidos_y_rechaza_raro():
    assert SB.normalize_tc(3.55) == 3.55
    assert SB.normalize_tc(1 / 3.55) == pytest.approx(3.55, abs=0.001)
    assert SB.normalize_tc(0.28) == pytest.approx(1 / 0.28, abs=0.001)
    assert SB.normalize_tc(10) is None
    assert SB.normalize_tc(2.0) is None
    assert SB.normalize_tc(0) is None
    assert SB.normalize_tc(None) is None
    assert SB.normalize_tc("3.55") == 3.55


def test_fantasma_spy_feriado_compra_el_siguiente_habil():
    spy = [{"date": "2026-01-02", "close": 100.0, "adjclose": 100.0},
           {"date": "2026-01-05", "close": 110.0, "adjclose": 110.0},   # 3 y 4 ene sin rueda
           {"date": "2026-01-09", "close": 120.0, "adjclose": 120.0}]
    rows = [{"kind": "deposito", "amount_usd": 100, "at": "2026-01-03"},
            {"kind": "retiro", "amount_usd": 60, "at": "2026-01-09"}]
    f = SB.fantasma_spy(rows, spy)
    shares = (100 - 0.15) / 110 - 60 / 120
    # sin brecha close/adjclose no hay dividendos: el resultado es el clásico
    assert f["acciones_fantasma"] == pytest.approx(shares, abs=1e-6)
    assert f["valor_fantasma"] == pytest.approx(shares * 120, abs=0.01)
    assert f["fecha_precio"] == "2026-01-09"
    assert any("más veces que el índice" in n for n in f["notas"])
    assert any("30 %" in n for n in f["notas"])


def test_fantasma_spy_descuenta_retencion_30pct_de_dividendos():
    # precio +10 % (100→110); retorno total +20 % (adjclose 100→120):
    # la componente de dividendos es ~10 % y el no residente solo cobra el 70 %.
    spy = [{"date": "2026-01-02", "close": 100.0, "adjclose": 100.0},
           {"date": "2026-01-05", "close": 110.0, "adjclose": 120.0}]
    rows = [{"kind": "deposito", "amount_usd": 100, "at": "2026-01-02"}]
    f = SB.fantasma_spy(rows, spy)
    esperado = (100 - 0.15) * (1 + 0.10 + 0.70 * 0.10)
    assert f["valor_fantasma"] == pytest.approx(esperado, abs=0.01)
    # bruto hubiera sido (100-0.15)*1.20: el neto queda por debajo
    assert f["valor_fantasma"] < (100 - 0.15) * 1.20


def test_fantasma_spy_sin_serie_o_sin_precio_devuelve_none():
    rows = [{"kind": "deposito", "amount_usd": 100, "at": "2026-01-03"}]
    assert SB.fantasma_spy(rows, []) is None
    assert SB.fantasma_spy(rows, None) is None
    # movimiento posterior al último precio conocido
    assert SB.fantasma_spy(rows, [{"date": "2026-01-02", "close": 100, "adjclose": 100}]) is None
    # filas sin adjclose o sin close no cuentan como dato
    assert SB.fantasma_spy(rows, [{"date": "2026-01-03", "close": 100, "adjclose": None}]) is None
    assert SB.fantasma_spy(rows, [{"date": "2026-01-03", "close": None, "adjclose": 100}]) is None
