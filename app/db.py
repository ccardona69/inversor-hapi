"""Capa de datos de Inversor Hapi IA: esquema SQLite y usuario único local."""
import os
import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("INVERSOR_DB", os.path.join(os.path.dirname(__file__), "..", "inversor.db"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
-- App local de un solo usuario: la fila de users solo existe para que el resto
-- de tablas puedan seguir filtrando por user_id.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
    salt TEXT NOT NULL, created_at TEXT NOT NULL
);
-- Módulo 1: posiciones. Cada dato marca su origen y si está verificado.
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT NOT NULL,
    name TEXT, sector TEXT, country TEXT, currency TEXT DEFAULT 'USD',
    qty REAL NOT NULL, avg_cost REAL, invested REAL,
    hapi_value REAL, hapi_pl REAL, hapi_return_pct REAL,
    source TEXT DEFAULT 'manual', verified INTEGER DEFAULT 0, notes TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT NOT NULL,
    side TEXT NOT NULL, qty REAL NOT NULL, price REAL NOT NULL, fees REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD', at TEXT NOT NULL, created_at TEXT NOT NULL
);
-- Procedencia adicional de operaciones importadas; las operaciones anteriores quedan intactas.
CREATE TABLE IF NOT EXISTS trade_sources (
    trade_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, source TEXT NOT NULL,
    model TEXT, order_id TEXT, fingerprint TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS trade_sources_user_fingerprint
    ON trade_sources(user_id, fingerprint);
CREATE TABLE IF NOT EXISTS cash (
    user_id INTEGER PRIMARY KEY, amount REAL DEFAULT 0, currency TEXT DEFAULT 'USD', updated_at TEXT
);
-- Módulo 3: todo precio guarda fuente, fecha/hora y moneda. Nunca se presenta
-- un dato viejo como actual: la API calcula 'stale' con la antigüedad.
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, price REAL NOT NULL,
    currency TEXT DEFAULT 'USD', asof TEXT NOT NULL, source TEXT NOT NULL,
    day_change_pct REAL, created_at TEXT NOT NULL
);
-- Fundamentales: ingreso manual (o import futura) SIEMPRE con fuente y fecha.
CREATE TABLE IF NOT EXISTS fundamentals (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT NOT NULL,
    data TEXT NOT NULL, source TEXT NOT NULL, asof TEXT NOT NULL, created_at TEXT NOT NULL,
    period TEXT, unit TEXT, shares_unit TEXT,
    UNIQUE(user_id, ticker)
);
-- Módulo 12: diario de inversión (antes y después de cada decisión)
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT, action TEXT,
    data TEXT NOT NULL, review_date TEXT, evaluation TEXT, created_at TEXT NOT NULL
);
-- Historial de decisiones propuestas/registradas (Módulos 7 y 15)
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT NOT NULL,
    proposal TEXT NOT NULL, user_choice TEXT, authorized INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
-- Módulo 10: candidatos del buscador de oportunidades (datos aportados por el usuario)
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, ticker TEXT NOT NULL,
    name TEXT, data TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT, PRIMARY KEY (user_id, key)
);
"""


def get_db() -> sqlite3.Connection:
    # WAL + busy_timeout: sin esto, dos solicitudes concurrentes (p. ej. la pantalla
    # Cartera pide /portfolio y /validate en paralelo) chocaban con «database is locked»
    # y devolvían 500. WAL deja que los lectores no bloqueen, y busy_timeout hace esperar
    # en vez de fallar. check_same_thread=False: la conexión vive dentro de una sola
    # solicitud, pero FastAPI la maneja desde su threadpool.
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fundamentals)")}
    for column in ("period", "unit", "shares_unit"):
        if column not in columns:
            conn.execute(f"ALTER TABLE fundamentals ADD COLUMN {column} TEXT")
    # Usuario local único al arrancar: así las solicitudes solo leen y no dejan
    # transacciones abiertas (hay endpoints que ejecutan BEGIN IMMEDIATE).
    conn.execute("INSERT INTO users (email, pw_hash, salt, created_at) "
                 "SELECT 'local', '', '', ? WHERE NOT EXISTS (SELECT 1 FROM users WHERE email='local')", (now(),))
    conn.commit()
    conn.close()


def local_user_id(conn) -> int:
    """Usuario único de la app (sin login): la cuenta 'local'. Las cuentas de la
    época con registro quedan intactas pero no se usan: la primera solía ser de prueba."""
    row = conn.execute("SELECT id FROM users WHERE email='local'").fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO users (email, pw_hash, salt, created_at) "
                       "VALUES ('local', '', '', ?)", (now(),))
    conn.commit()  # el INSERT no puede quedar pendiente: hay endpoints con BEGIN IMMEDIATE
    return cur.lastrowid


def get_setting(conn, user_id, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (TypeError, json.JSONDecodeError):
        return row["value"]


def set_setting(conn, user_id, key, value):
    conn.execute("INSERT INTO settings (user_id, key, value) VALUES (?,?,?) "
                 "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
                 (user_id, key, json.dumps(value, ensure_ascii=False)))


def cash_upsert(conn, user_id, amount):
    conn.execute("INSERT INTO cash (user_id, amount, currency, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT(user_id) DO UPDATE SET amount=excluded.amount, "
                 "currency=excluded.currency, updated_at=excluded.updated_at",
                 (user_id, amount, "USD", now()))


def latest_price(conn, ticker):
    row = conn.execute("SELECT * FROM prices WHERE ticker=? ORDER BY asof DESC, id DESC LIMIT 1",
                       (ticker.upper(),)).fetchone()
    return dict(row) if row else None
