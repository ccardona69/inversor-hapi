"""Alcancía EOQ en soles: cálculos puros, sin BD ni red."""
import pytest

from app import alcancia as AL


def test_eoq():
    assert AL.eoq(270.42, 0.05, 3) == pytest.approx(1.50, abs=0.01)


def test_plan_80_soles_declarado():
    """Sin datos de ahorro el mensual declarado entra como ESTIMACIÓN."""
    p = AL.plan([], r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["ahorro_estimado"] is True and p["ahorro_mensual"] == 80
    assert p["n_optimo"] == pytest.approx(1.50, abs=0.01)
    assert p["n_practico"] == 2
    assert p["meta_usd"] == pytest.approx(135.21, abs=0.01)
    assert p["meta_soles"] == pytest.approx(480, abs=0.5)
    assert p["optimo_soles"] == pytest.approx(639.5, abs=1)
    assert p["meses_por_deposito"] == pytest.approx(6, abs=0.1)
    assert p["faltan_meses"] == 6 and p["llego_meta"] is False


def test_plan_progreso_conserva_el_sobrante():
    """Ahorraste S/500, enviaste S/480 → arrancas con S/20, no con 0."""
    rows = [{"kind": "ahorro_soles", "soles_amount": 500, "at": "2026-09-01"},
            {"kind": "deposito", "soles_amount": 480, "amount_usd": 132.5,
             "at": "2026-09-02"}]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["progreso"] == 20
    assert p["ahorrado_soles"] == 500 and p["enviado_soles"] == 480


def test_plan_progreso_nunca_negativo():
    rows = [{"kind": "ahorro_soles", "soles_amount": 100, "at": "2026-09-01"},
            {"kind": "deposito", "soles_amount": 480, "amount_usd": 132.5,
             "at": "2026-09-02"}]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["progreso"] == 0


def test_plan_menos_de_dos_meses_es_estimado():
    rows = [{"kind": "ahorro_soles", "soles_amount": 80, "at": "2026-09-16"}]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["ahorro_estimado"] is True and p["ahorro_mensual"] == 80


def test_plan_mensual_desde_datos_reales():
    rows = [{"kind": "ahorro_soles", "soles_amount": 80, "at": d}
            for d in ("2026-01-05", "2026-02-05", "2026-03-05")]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=999, today="2026-04-05")
    assert p["ahorro_estimado"] is False and p["ahorro_mensual"] != 999
    # 90 días / 30.44 ≈ 2.96 meses → S/240 ÷ 2.96 ≈ 81
    assert p["ahorro_mensual"] == pytest.approx(81, abs=1)


def test_plan_faltan_meses_con_progreso():
    rows = [{"kind": "ahorro_soles", "soles_amount": 160, "at": "2026-09-10"}]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["faltan_meses"] == 4  # ceil((480 − 160) / 80)


def test_plan_llego_meta():
    rows = [{"kind": "ahorro_soles", "soles_amount": 500, "at": "2026-09-10"}]
    p = AL.plan(rows, r=0.05, fee=3, fx=3.55, declarado_mensual=80, today="2026-09-26")
    assert p["llego_meta"] is True and p["faltan_meses"] == 0


def test_plan_sin_ahorro_no_inventa():
    p = AL.plan([], r=0.05, fee=3, fx=3.55, declarado_mensual=0, today="2026-09-26")
    assert p["meta_soles"] is None and p["llego_meta"] is False
