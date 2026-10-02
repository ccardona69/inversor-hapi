"""brecha.py: regla del plan (fuente única), brecha ETF y proyección.
Cálculos puros, sin BD ni red."""
import pytest

from app import brecha as BR


# ---------- regla_plan ----------

def test_regla_compra_accion_bajo_meta_no_cumple():
    r = BR.regla_plan(tickers=["BBB"], lado="comprar", meta_pct=50, etf_pct=0.0)
    assert r["aplica"] is True and r["regla"] == "R1" and r["cumple"] is False
    assert r["motivo"] == "etf_bajo_meta"


def test_regla_compra_accion_en_meta_cumple():
    r = BR.regla_plan(tickers=["BBB"], lado="comprar", meta_pct=50, etf_pct=55.0)
    assert r["aplica"] is True and r["cumple"] is True


def test_regla_compra_etf_y_venta_accion_siempre_cumplen():
    assert BR.regla_plan(tickers=["VOO"], lado="comprar", meta_pct=50,
                         etf_pct=0.0)["aplica"] is False
    assert BR.regla_plan(tickers=["AAPL"], lado="vender", meta_pct=50,
                         etf_pct=0.0)["aplica"] is False


def test_regla_qqq_y_dia_cuentan_como_accion():
    """Solo los índices amplios (ETF_META) cuentan para la meta: QQQ
    concentraría las mismas megacaps; venderlo no dispara el aviso de ETF."""
    r = BR.regla_plan(tickers=["QQQ"], lado="comprar", meta_pct=50,
                      etf_pct=0.0)
    assert r["aplica"] is True and r["cumple"] is False
    r = BR.regla_plan(tickers=["QQQ"], lado="vender", meta_pct=50,
                      valor_etf=500, valor_base=1500, monto_usd=250)
    assert r["aplica"] is False and r["aviso"] is None


def test_regla_r1_prima_evalua_el_despues():
    """Caso D del plan: 51 % en meta, compra de $500 en acción → 48.57 %."""
    r = BR.regla_plan(tickers=["AAPL"], lado="comprar", meta_pct=50,
                      valor_etf=5100, valor_base=10000, monto_usd=500)
    assert r["regla"] == "R1'" and r["cumple"] is False
    assert r["etf_pct_antes"] == 51.0
    assert r["etf_pct_despues"] == pytest.approx(48.57, abs=0.01)
    assert r["margen_acciones_usd"] == 200.0


def test_regla_venta_etf_bajo_meta_avisa_sin_bloquear():
    r = BR.regla_plan(tickers=["SPY"], lado="vender", meta_pct=50,
                      valor_etf=500, valor_base=1500, monto_usd=250)
    assert r["aplica"] is True and r["cumple"] is True
    assert r["etf_pct_despues"] == pytest.approx(20.0, abs=0.01)
    assert "meta" in r["aviso"]


def test_regla_sin_dato_es_fail_closed():
    """etf_pct None cuenta como bajo la meta (igual que el guard del chat)."""
    assert BR.regla_plan(tickers=["BBB"], lado="comprar", meta_pct=50,
                         etf_pct=None)["cumple"] is False
    r = BR.regla_plan(tickers=["BBB"], lado="comprar", meta_pct=50,
                      valor_etf=0, valor_base=None, monto_usd=100)
    assert r["etf_pct_despues"] is None and r["cumple"] is False


# ---------- brecha ----------

def test_brecha_caso_a_lejano():
    """B=10000, E=3000, D=300 → todo al ETF; quedan ~14 aportes a $300."""
    b = BR.brecha(valor_base=10000, valor_etf=3000, meta_pct=50, a_invertir_usd=300)
    assert b["brecha_usd"] == 2000.0 and b["a_etf_usd"] == 300.0
    assert b["libre_usd"] == 0.0 and b["en_meta"] is False
    assert b["etf_pct_despues"] == pytest.approx(32.04, abs=0.01)


def test_brecha_caso_b_cierra_dentro_del_aporte():
    b = BR.brecha(valor_base=10000, valor_etf=4900, meta_pct=50, a_invertir_usd=300)
    assert b["a_etf_usd"] == 250.0 and b["libre_usd"] == 50.0
    assert b["etf_pct_despues"] == pytest.approx(50.0, abs=0.01)
    assert b["brecha_despues_usd"] == 0.0


def test_brecha_dinero_nuevo_es_el_doble_de_la_venta():
    """Caso real: B=1012.2 todo en acciones, meta 50 %. La brecha ($506.10)
    es lo que habría que vender; por aportes hace falta el doble ($1012.20)
    porque cada USD nuevo también agranda la base."""
    b = BR.brecha(valor_base=1012.2, valor_etf=0, meta_pct=50)
    assert b["brecha_usd"] == 506.1
    assert b["dinero_nuevo_para_meta_usd"] == 1012.2


def test_brecha_caso_c_en_meta_margen_libre():
    b = BR.brecha(valor_base=10000, valor_etf=6000, meta_pct=50, a_invertir_usd=300)
    assert b["a_etf_usd"] == 0.0 and b["libre_usd"] == 300.0
    assert b["en_meta"] is True and b["margen_acciones_usd"] == 2000.0


def test_brecha_base_cero_todo_al_etf_segun_meta():
    """Cartera vacía: con meta 50 % la mitad del dinero nuevo va al ETF."""
    b = BR.brecha(valor_base=0, valor_etf=0, meta_pct=50, a_invertir_usd=100)
    assert b["etf_pct"] is None and b["en_meta"] is False
    assert b["a_etf_usd"] == 50.0 and b["etf_pct_despues"] == 50.0


def test_brecha_propiedad_cero_si_en_meta():
    """Para B>0 y 0≤E≤B: brecha_usd == 0  ⇔  100·E/B ≥ meta."""
    for B in (100, 1000, 10000):
        for meta in (0, 25, 50, 75, 100):
            for E in (0, B * 0.3, B * 0.5, B * 0.8, B):
                b = BR.brecha(valor_base=B, valor_etf=E, meta_pct=meta)
                assert (b["brecha_usd"] == 0) == (100 * E / B >= meta - 1e-9)


def test_brecha_propiedad_x_estrella_cierra_en_meta():
    """Si 0 < X* ≤ D, etf_pct_despues queda exactamente en la meta."""
    for B in (1000, 5000):
        for E in (B * 0.3, B * 0.49):
            for meta in (50, 60):
                x = meta / 100 * (B + 500) - E
                if 0 < x <= 500:
                    b = BR.brecha(valor_base=B, valor_etf=E, meta_pct=meta,
                                  a_invertir_usd=500)
                    assert b["etf_pct_despues"] == pytest.approx(meta, abs=0.05)


# ---------- proyeccion ----------

def test_proyeccion_tres_rutas_siempre_estimacion():
    p = BR.proyeccion(brecha_usd=2000, meta_pct=50, aporte_tipico_usd=300,
                      meses_por_deposito=6, aporte_alternativo_usd=600)
    assert p["etiqueta"] == "ESTIMACIÓN"
    # cada aporte cierra a·(1−t) = 150 → ceil(2000/150) = 14
    assert p["despacio"] == {"aportes": 14, "meses": 84.0}
    assert p["ahorrar_mas"] == {"aportes": 7, "meses": 42.0}
    assert p["rebalancear"]["venta_usd"] == 2000.0
    assert "efecto fiscal" in p["rebalancear"]["nota"]


def test_proyeccion_bordes():
    # meta 100: imposible por aportes → despacio None
    p = BR.proyeccion(brecha_usd=100, meta_pct=100, aporte_tipico_usd=50,
                      meses_por_deposito=6)
    assert p["despacio"] is None
    # brecha 0 → cero aportes; rebalancear None
    p = BR.proyeccion(brecha_usd=0, meta_pct=50, aporte_tipico_usd=300,
                      meses_por_deposito=6)
    assert p["despacio"] == {"aportes": 0, "meses": 0.0}
    assert p["rebalancear"] is None
