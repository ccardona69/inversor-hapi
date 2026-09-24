"""Flujos confirmados de Luna; nunca importa app.main con la base real."""
import os
import tempfile
from decimal import Decimal
from datetime import datetime, timedelta, timezone

os.environ["INVERSOR_DB"] = os.path.join(tempfile.mkdtemp(), "luna-import.db")

import pytest
from fastapi.testclient import TestClient

from app import db as D
from app import marketdata as MD
from app import fundsync as FS
from app import tradesync as TS
from app import ai_review as RV
from app.main import app


@pytest.fixture
def users(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "DB_PATH", str(tmp_path / "users.db"))
    D.init_db()
    alice, bob = TestClient(app), TestClient(app)
    for client, email in ((alice, "alice@test.org"), (bob, "bob@test.org")):
        assert client.post("/api/register", json={"email": email, "password": "test-secret-1"}).status_code == 200
    return alice, bob


def count(table):
    conn = D.get_db()
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def trade(**changes):
    return {"ticker": "AAA", "side": "comprar", "qty": "2", "price": "10",
            "fees": "0", "currency": "USD", "at": "2025-01-01", **changes}


def import_rows(client, rows, **changes):
    return client.post("/api/trades/import", json={**{"rows": rows, "source": "Hapi, captura revisada por usuario",
                                                    "reviewed": True}, **changes})


def test_previews_require_auth_image_and_never_write(users, monkeypatch):
    alice, _ = users
    anonymous = TestClient(app)
    for path in ("/api/fundamentals/photo/analyze", "/api/trades/photo/analyze"):
        assert anonymous.post(path, json={"image_b64": "YQ==", "mime": "image/png"}).status_code == 401
        assert alice.post(path, json={"image_b64": "invalid", "mime": "image/png"}).status_code == 400
        assert alice.post(path, json={"image_b64": "YQ==", "mime": "text/plain"}).status_code == 400
    monkeypatch.setattr(FS, "analyze", lambda *args: {"data": {"revenue": 12}, "model": "mock"})
    monkeypatch.setattr(TS, "analyze", lambda *args: {"rows": [trade()], "omitted": ["not visible"], "model": "mock"})
    before = {table: count(table) for table in ("audit_log", "trades", "trade_sources", "fundamentals")}
    for path in ("/api/fundamentals/photo/analyze", "/api/trades/photo/analyze"):
        assert alice.post(path, json={"image_b64": "YQ==", "mime": "image/png"}).status_code == 200
    assert before == {table: count(table) for table in before}
    def fail(*args):
        raise FS.FundSyncError("proveedor no disponible")
    monkeypatch.setattr(FS, "analyze", fail)
    assert alice.post("/api/fundamentals/photo/analyze", json={"image_b64": "YQ==", "mime": "image/png"}).status_code == 502
    monkeypatch.setattr(TS, "analyze", lambda *args: (_ for _ in ()).throw(TS.TradeSyncError("sin respuesta")))
    assert alice.post("/api/trades/photo/analyze", json={"image_b64": "YQ==", "mime": "image/png"}).status_code == 502


def test_fundamentals_confirmed_units_period_and_replacement(users, monkeypatch):
    alice, bob = users
    monkeypatch.setattr(FS, "analyze", lambda *args: (_ for _ in ()).throw(AssertionError("No llamar al modelo")))
    payload = {"data": {"revenue": "12", "shares_out": "2", "eps": "3"},
               "source": "Informe 10-K revisado", "asof": "2025-01-01", "period": "anual",
               "unit": "millones USD", "shares_unit": "miles acciones"}
    path = "/api/fundamentals/AAA/photo/save"
    invalid = ({"source": " "}, {"asof": "no-date"},
               {"asof": (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()},
               {"period": "trimestral"}, {"unit": None}, {"shares_unit": None})
    for change in invalid:
        assert alice.post(path, json={**payload, **change}).status_code == 400
    assert count("fundamentals") == 0
    saved = alice.post(path, json=payload)
    assert saved.status_code == 200, saved.text
    data = alice.get("/api/fundamentals/AAA").json()
    assert data["fundamentals"] == {"revenue": 12_000_000, "shares_out": 2_000, "eps": 3}
    assert (data["source"], data["asof"], data["period"], data["unit"], data["shares_unit"]) == (
        payload["source"], payload["asof"], "anual", "millones USD", "miles acciones")
    assert bob.get("/api/fundamentals/AAA").json()["fundamentals"] == {}
    assert alice.post(path, json={**payload, "data": {"fcf": 1}}).status_code == 400
    changed = alice.post(path, json={**payload, "data": {"fcf": "4"}, "period": "TTM",
                                     "replace_existing": True})
    assert changed.status_code == 200, changed.text
    assert alice.get("/api/fundamentals/AAA").json()["fundamentals"] == {"fcf": 4_000_000}
    assert alice.put("/api/fundamentals/AAA", json={"data": {"eps": 1}, "source": "Manual",
                                                    "asof": "2025-02-01"}).status_code == 200
    manual = alice.get("/api/fundamentals/AAA").json()
    assert manual["period"] is None and manual["unit"] is None and manual["shares_unit"] is None
    assert count("audit_log") >= 2


def test_trade_import_is_atomic_and_tracks_provenance_and_duplicates(users):
    alice, bob = users
    assert TestClient(app).post("/api/trades/import", json={}).status_code == 401
    assert import_rows(alice, [trade()], reviewed=False).status_code == 400
    for incomplete in (trade(fees=None), trade(at=None), trade(currency=None),
                       trade(price="inf")):
        assert import_rows(alice, [trade(), incomplete]).status_code == 400
    assert count("trades") == count("trade_sources") == 0
    assert import_rows(alice, [trade(), trade()]).status_code == 400
    assert count("trades") == 0
    first = import_rows(alice, [trade(order_id="hapi-1")])
    assert first.status_code == 200, first.text
    assert first.json()["imported"] == 1
    listed = alice.get("/api/trades?ticker=AAA").json()["trades"]
    assert len(listed) == 1 and listed[0]["source"] == "Hapi, captura revisada por usuario — confirmado por usuario"
    assert listed[0]["order_id"] == "hapi-1" and listed[0]["fingerprint"] and listed[0]["imported_at"]
    assert listed[0]["at"] == "2025-01-01" and listed[0]["currency"] == "USD"
    assert bob.get("/api/trades").json()["trades"] == []
    assert import_rows(alice, [trade(order_id="hapi-1"), trade(at="2025-02-01")]).status_code == 400
    assert count("trades") == 1
    assert import_rows(alice, [trade(order_id="hapi-1", price="11")]).status_code == 400
    repeated = import_rows(alice, [trade(order_id="hapi-1"), trade(order_id="hapi-1")], allow_duplicates=True)
    assert repeated.status_code == 200 and len(repeated.json()["duplicates"]) == 2
    assert repeated.json()["warnings"] and count("trades") == count("trade_sources") == 3
    # Misma huella sin order_id puede corresponder a dos órdenes reales: no descartar silenciosamente.
    assert import_rows(bob, [trade(), trade()]).status_code == 400
    assert import_rows(bob, [trade(), trade()], allow_duplicates=True).json()["imported"] == 2
    assert len(bob.get("/api/trades?ticker=AAA").json()["trades"]) == 2


def test_reconcile_requires_complete_traceable_ledger_and_verified_qty(users):
    alice, bob = users
    assert alice.post("/api/positions", json={"ticker": "AAA", "qty": 2, "avg_cost": 1,
                                               "source": "usuario"}).status_code == 200
    assert import_rows(alice, [trade()]).status_code == 200
    endpoint = "/api/trades/AAA/reconcile"
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400
    assert alice.post("/api/positions/AAA/verify").status_code == 200
    assert alice.post(endpoint, json={"complete_history": False}).status_code == 400
    assert bob.post(endpoint, json={"complete_history": True}).status_code == 400
    baseline = count("audit_log")
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400
    preview = alice.post(endpoint, json={"complete_history": True, "confirmed_qty": "2"})
    assert preview.status_code == 200, preview.text
    assert Decimal(preview.json()["qty"]) == 2 and Decimal(preview.json()["invested"]) == 20
    assert Decimal(preview.json()["avg_cost"]) == 10 and preview.json()["position_qty"] == 2
    assert preview.json()["preview_token"] and preview.json()["reconciled"]
    assert "SQLite" in preview.json()["warning"] and count("audit_log") == baseline
    assert alice.post(endpoint, json={"complete_history": True, "apply": True}).status_code == 400
    assert alice.post(endpoint, json={"complete_history": True, "apply": True,
                                      "confirmed_qty": 3, "preview_token": preview.json()["preview_token"]}).status_code == 400
    assert alice.post(endpoint, json={"complete_history": True, "apply": True,
                                      "confirmed_qty": 2}).status_code == 400
    assert alice.post(endpoint, json={"complete_history": True, "apply": True,
                                      "confirmed_qty": 2,
                                      "preview_token": preview.json()["preview_token"]}).status_code == 400
    assert alice.post(endpoint, json={"complete_history": True, "apply": True,
                                      "no_unmodeled_adjustments": True, "confirmed_qty": 2,
                                      "preview_token": preview.json()["preview_token"]}).status_code == 200
    pos = alice.get("/api/portfolio").json()["positions"][0]
    assert pos["qty"] == 2 and pos["avg_cost"] == 10 and pos["invested"] == 20 and pos["verified"] == 0
    assert alice.post(endpoint, json={"complete_history": True, "apply": True,
                                      "confirmed_qty": 2,
                                      "preview_token": preview.json()["preview_token"]}).status_code == 400


def test_reconcile_never_applies_an_unreviewed_updated_ledger(users):
    alice, _ = users
    assert alice.post("/api/positions", json={"ticker": "AAA", "qty": 2,
                                               "avg_cost": 10, "source": "Hapi"}).status_code == 200
    assert alice.post("/api/positions/AAA/verify").status_code == 200
    assert import_rows(alice, [trade()]).status_code == 200
    endpoint = "/api/trades/AAA/reconcile"
    body = {"complete_history": True, "confirmed_qty": "2"}
    preview = alice.post(endpoint, json=body).json()
    assert import_rows(alice, [trade(qty="1", price="30", at="2025-02-01"),
                               trade(side="vender", qty="1", at="2025-03-01")]).status_code == 200
    stale = alice.post(endpoint, json={**body, "apply": True, "no_unmodeled_adjustments": True,
                                        "preview_token": preview["preview_token"]})
    assert stale.status_code == 400 and "vista previa" in stale.json()["detail"]
    pos = alice.get("/api/portfolio").json()["positions"][0]
    assert pos["invested"] == 20 and pos["verified"] == 1
    updated = alice.post(endpoint, json=body).json()
    assert updated["preview_token"] != preview["preview_token"]
    applied = alice.post(endpoint, json={**body, "apply": True, "no_unmodeled_adjustments": True,
                                         "preview_token": updated["preview_token"]})
    assert applied.status_code == 200, applied.text
    assert alice.get("/api/portfolio").json()["positions"][0]["avg_cost"] != 10


def test_reconcile_blocks_missing_provenance_oversell_ambiguity_and_qty_mismatch(users):
    alice, _ = users
    assert alice.post("/api/positions", json={"ticker": "AAA", "qty": 2, "source": "manual"}).status_code == 200
    assert alice.post("/api/positions/AAA/verify").status_code == 200
    assert import_rows(alice, [trade()]).status_code == 200
    endpoint = "/api/trades/AAA/reconcile"
    conn = D.get_db()
    try:
        conn.execute("INSERT INTO trades (user_id,ticker,side,qty,price,fees,currency,at,created_at) "
                     "VALUES (1,'AAA','comprar',1,10,0,'USD','2025-01-02',?)", (D.now(),))
        conn.commit()
        legacy = conn.execute("SELECT max(id) FROM trades").fetchone()[0]
    finally:
        conn.close()
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400
    conn = D.get_db()
    try:
        conn.execute("DELETE FROM trades WHERE id=?", (legacy,))
        conn.commit()
    finally:
        conn.close()
    assert import_rows(alice, [trade(side="vender", qty="3", at="2025-01-02")]).status_code == 200
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400
    conn = D.get_db()
    try:
        conn.execute("DELETE FROM trade_sources WHERE trade_id IN (SELECT id FROM trades WHERE side='vender')")
        conn.execute("DELETE FROM trades WHERE side='vender'")
        conn.commit()
    finally:
        conn.close()
    assert import_rows(alice, [trade(side="vender", qty="1")]).status_code == 200
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400  # same-day ambiguity
    conn = D.get_db()
    try:
        conn.execute("UPDATE trades SET at='2025-01-02' WHERE side='vender'")
        conn.commit()
    finally:
        conn.close()
    assert alice.post(endpoint, json={"complete_history": True}).status_code == 400  # qty=1, verified=2


def test_reviews_use_saved_user_rows_without_writes_or_reanalysis(users, monkeypatch):
    alice, bob = users
    entry = alice.post("/api/journal", json={"ticker": "AAA", "tesis": "Tesis comprobable", "fuentes": "Informe"}).json()["id"]
    assert alice.post("/api/prices/manual", json={"ticker": "AAA", "price": 10,
        "source": "bróker", "asof": datetime.now(timezone.utc).isoformat(timespec="seconds")}).status_code == 200
    monkeypatch.setattr(MD, "fetch_history", lambda ticker: (_ for _ in ()).throw(MD.MarketDataError("offline")))
    decision = alice.post("/api/analysis/AAA", json={})
    assert decision.status_code == 200, decision.text
    did = decision.json()["decision_id"]
    saved = alice.get("/api/decisions").json()["decisions"][0]["proposal"]
    assert saved["argumentos"] == decision.json()["decision"]["argumentos"]
    assert saved["precio_fuente"] == "bróker" and saved["precio_asof"]
    seen = {}
    monkeypatch.setattr(RV, "challenge", lambda data: seen.setdefault("entry", data) or {"ok": True})
    def explain(report):
        seen["report"] = report
        return {"explanation": "Explicación verificada", "model": "mock"}
    monkeypatch.setattr(RV, "explain", explain)
    baseline = count("audit_log")
    assert bob.post(f"/api/journal/{entry}/challenge").status_code == 404
    assert bob.post(f"/api/decisions/{did}/explain").status_code == 404
    assert alice.post(f"/api/journal/{entry}/challenge").status_code == 200
    assert alice.post(f"/api/decisions/{did}/explain").status_code == 200
    assert seen["entry"]["tesis"] == "Tesis comprobable"
    assert seen["report"]["argumentos"] == saved["argumentos"]
    assert count("audit_log") == baseline
    monkeypatch.setattr(RV, "explain", lambda report: (_ for _ in ()).throw(RV.ReviewError("proveedor")))
    assert alice.post(f"/api/decisions/{did}/explain").status_code == 502
    conn = D.get_db()
    try:
        conn.execute("UPDATE decisions SET proposal=? WHERE id=?", ('{"decision":"esperar"}', did))
        conn.execute("UPDATE journal SET data=? WHERE id=?", ('{"tesis":""}', entry))
        conn.commit()
    finally:
        conn.close()
    assert alice.post(f"/api/decisions/{did}/explain").status_code == 400
    assert alice.post(f"/api/journal/{entry}/challenge").status_code == 400


def test_delete_all_clears_only_own_trade_provenance(users):
    alice, bob = users
    assert import_rows(alice, [trade()]).status_code == 200
    assert import_rows(bob, [trade()]).status_code == 200
    assert alice.post("/api/settings/delete_all", json={"confirm": "ELIMINAR"}).status_code == 200
    assert count("trade_sources") == 1 and count("trades") == 1
    assert bob.get("/api/trades").json()["trades"][0]["source"]
