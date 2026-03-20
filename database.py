import os
import json
from datetime import datetime

# Detectar si usar PostgreSQL o SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES  = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

from config import DB_PATH


def get_conn():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(DB_PATH)


def placeholder(n=1):
    """Retorna placeholders correctos según el motor."""
    if USE_POSTGRES:
        return ", ".join(["%s"] * n)
    return ", ".join(["?"] * n)


def ph():
    return "%s" if USE_POSTGRES else "?"


def init_db():
    conn = get_conn()
    c    = conn.cursor()

    if USE_POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS bankroll (
                id        SERIAL PRIMARY KEY,
                timestamp TEXT    NOT NULL,
                balance   REAL    NOT NULL,
                nota      TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS apuestas (
                id          SERIAL PRIMARY KEY,
                timestamp   TEXT    NOT NULL,
                sport       TEXT    NOT NULL,
                partido     TEXT    NOT NULL,
                mercado     TEXT    NOT NULL,
                seleccion   TEXT    NOT NULL,
                cuota       REAL    NOT NULL,
                monto       REAL    NOT NULL,
                confianza   REAL    NOT NULL,
                razon       TEXT,
                resultado   TEXT    DEFAULT 'pendiente',
                ganancia    REAL    DEFAULT 0.0,
                semana      TEXT    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS semanas (
                semana           TEXT PRIMARY KEY,
                apuestas_total   INTEGER DEFAULT 0,
                apuestas_ganadas INTEGER DEFAULT 0,
                invertido        REAL    DEFAULT 0.0,
                retorno          REAL    DEFAULT 0.0,
                roi              REAL    DEFAULT 0.0,
                es_negativa      INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS estado_agente (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS bankroll (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                balance   REAL    NOT NULL,
                nota      TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS apuestas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                sport       TEXT    NOT NULL,
                partido     TEXT    NOT NULL,
                mercado     TEXT    NOT NULL,
                seleccion   TEXT    NOT NULL,
                cuota       REAL    NOT NULL,
                monto       REAL    NOT NULL,
                confianza   REAL    NOT NULL,
                razon       TEXT,
                resultado   TEXT    DEFAULT 'pendiente',
                ganancia    REAL    DEFAULT 0.0,
                semana      TEXT    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS semanas (
                semana           TEXT PRIMARY KEY,
                apuestas_total   INTEGER DEFAULT 0,
                apuestas_ganadas INTEGER DEFAULT 0,
                invertido        REAL    DEFAULT 0.0,
                retorno          REAL    DEFAULT 0.0,
                roi              REAL    DEFAULT 0.0,
                es_negativa      INTEGER DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS estado_agente (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        """)

    conn.commit()
    conn.close()
    print(f"[DB] Inicializada ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")


def semana_actual():
    return datetime.now().strftime("%Y-W%W")


def _fetchall_as_dicts(cursor, rows, cols):
    return [dict(zip(cols, r)) for r in rows]


# ---- Bankroll ----

def registrar_bankroll(balance: float, nota: str = ""):
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        f"INSERT INTO bankroll (timestamp, balance, nota) VALUES ({placeholder(3)})",
        (datetime.now().isoformat(), balance, nota)
    )
    conn.commit()
    conn.close()


def get_balance_actual() -> float:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT balance FROM bankroll ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0


# ---- Apuestas ----

def registrar_apuesta(data: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"""
        INSERT INTO apuestas
        (timestamp, sport, partido, mercado, seleccion, cuota, monto, confianza, razon, semana)
        VALUES ({placeholder(10)})
    """, (
        datetime.now().isoformat(),
        data["sport"], data["partido"], data["mercado"],
        data["seleccion"], data["cuota"], data["monto"],
        data["confianza"], data.get("razon",""), semana_actual()
    ))
    if USE_POSTGRES:
        c.execute("SELECT lastval()")
    apuesta_id = c.fetchone()[0] if USE_POSTGRES else c.lastrowid
    conn.commit()
    conn.close()
    return apuesta_id


def actualizar_resultado(apuesta_id: int, resultado: str, ganancia: float):
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        f"UPDATE apuestas SET resultado = {ph()}, ganancia = {ph()} WHERE id = {ph()}",
        (resultado, ganancia, apuesta_id)
    )
    conn.commit()
    conn.close()


def get_apuestas_pendientes() -> list:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT * FROM apuestas WHERE resultado = 'pendiente'")
    rows = c.fetchall()
    conn.close()
    cols = ["id","timestamp","sport","partido","mercado","seleccion",
            "cuota","monto","confianza","razon","resultado","ganancia","semana"]
    return [dict(zip(cols, r)) for r in rows]


# ---- Semanas ----

def actualizar_semana(semana: str):
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        f"SELECT resultado, monto, ganancia FROM apuestas WHERE semana = {ph()} AND resultado != 'pendiente'",
        (semana,)
    )
    rows     = c.fetchall()
    total    = len(rows)
    ganadas  = sum(1 for r in rows if r[0] == "ganada")
    invertido = sum(r[1] for r in rows)
    retorno  = sum(r[2] for r in rows)
    roi      = (retorno / invertido) if invertido > 0 else 0.0
    negativa = 1 if roi < -0.05 else 0

    if USE_POSTGRES:
        c.execute("""
            INSERT INTO semanas (semana, apuestas_total, apuestas_ganadas, invertido, retorno, roi, es_negativa)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (semana) DO UPDATE SET
                apuestas_total   = EXCLUDED.apuestas_total,
                apuestas_ganadas = EXCLUDED.apuestas_ganadas,
                invertido        = EXCLUDED.invertido,
                retorno          = EXCLUDED.retorno,
                roi              = EXCLUDED.roi,
                es_negativa      = EXCLUDED.es_negativa
        """, (semana, total, ganadas, invertido, retorno, roi, negativa))
    else:
        c.execute("""
            INSERT INTO semanas (semana, apuestas_total, apuestas_ganadas, invertido, retorno, roi, es_negativa)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(semana) DO UPDATE SET
                apuestas_total   = excluded.apuestas_total,
                apuestas_ganadas = excluded.apuestas_ganadas,
                invertido        = excluded.invertido,
                retorno          = excluded.retorno,
                roi              = excluded.roi,
                es_negativa      = excluded.es_negativa
        """, (semana, total, ganadas, invertido, retorno, roi, negativa))

    conn.commit()
    conn.close()


def contar_semanas_negativas_consecutivas() -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT es_negativa FROM semanas ORDER BY semana DESC LIMIT 5")
    rows  = c.fetchall()
    conn.close()
    count = 0
    for (neg,) in rows:
        if neg == 1:
            count += 1
        else:
            break
    return count


def get_stats_globales() -> dict:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN resultado='ganada' THEN 1 ELSE 0 END) as ganadas,
            SUM(monto) as invertido,
            SUM(ganancia) as retorno
        FROM apuestas WHERE resultado != 'pendiente'
    """)
    row = c.fetchone()
    conn.close()
    total, ganadas, invertido, retorno = row
    total     = total    or 0
    ganadas   = ganadas  or 0
    invertido = invertido or 0.0
    retorno   = retorno  or 0.0
    return {
        "total":     total,
        "ganadas":   ganadas,
        "winrate":   round(ganadas / total, 3) if total > 0 else 0,
        "invertido": round(float(invertido), 2),
        "retorno":   round(float(retorno), 2),
        "roi":       round(float(retorno) / float(invertido), 3) if invertido else 0
    }


# ---- Estado ----

def set_estado(clave: str, valor: str):
    conn = get_conn()
    c    = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            INSERT INTO estado_agente (clave, valor) VALUES (%s, %s)
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
        """, (clave, valor))
    else:
        c.execute("INSERT OR REPLACE INTO estado_agente (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()


def get_estado(clave: str, default=None) -> str:
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"SELECT valor FROM estado_agente WHERE clave = {ph()}", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default
