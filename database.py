import os
from datetime import datetime, date

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


def ph():
    return "%s" if USE_POSTGRES else "?"


def placeholder(n=1):
    p = "%s" if USE_POSTGRES else "?"
    return ", ".join([p] * n)


def query(sql, params=()):
    conn = get_conn()
    c    = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows


def execute(sql, params=()):
    conn = get_conn()
    c    = conn.cursor()
    c.execute(sql, params)
    result = None
    if USE_POSTGRES and "RETURNING" in sql.upper():
        result = c.fetchone()
    elif not USE_POSTGRES:
        result = c.lastrowid
    conn.commit()
    conn.close()
    return result


def init_db():
    conn = get_conn()
    c    = conn.cursor()
    serial = "SERIAL" if USE_POSTGRES else "INTEGER"
    pk     = "PRIMARY KEY" if not USE_POSTGRES else ""

    tables = [
        f"""CREATE TABLE IF NOT EXISTS bankroll (
            id        {'SERIAL PRIMARY KEY' if USE_POSTGRES else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            timestamp TEXT NOT NULL,
            balance   REAL NOT NULL,
            nota      TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS apuestas (
            id          {'SERIAL PRIMARY KEY' if USE_POSTGRES else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            timestamp   TEXT NOT NULL,
            fecha       TEXT NOT NULL,
            sport       TEXT NOT NULL,
            partido     TEXT NOT NULL,
            mercado     TEXT NOT NULL,
            seleccion   TEXT NOT NULL,
            cuota       REAL NOT NULL,
            monto       REAL NOT NULL,
            confianza   REAL NOT NULL,
            razon       TEXT,
            aprendizaje TEXT,
            resultado   TEXT DEFAULT 'pendiente',
            ganancia    REAL DEFAULT 0.0,
            semana      TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS dias (
            fecha            TEXT PRIMARY KEY,
            apuestas_total   INTEGER DEFAULT 0,
            apuestas_ganadas INTEGER DEFAULT 0,
            invertido        REAL DEFAULT 0.0,
            retorno          REAL DEFAULT 0.0,
            roi              REAL DEFAULT 0.0,
            es_negativo      INTEGER DEFAULT 0
        )""",
        f"""CREATE TABLE IF NOT EXISTS semanas (
            semana           TEXT PRIMARY KEY,
            apuestas_total   INTEGER DEFAULT 0,
            apuestas_ganadas INTEGER DEFAULT 0,
            invertido        REAL DEFAULT 0.0,
            retorno          REAL DEFAULT 0.0,
            roi              REAL DEFAULT 0.0,
            es_negativa      INTEGER DEFAULT 0
        )""",
        f"""CREATE TABLE IF NOT EXISTS estado_agente (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )""",
    ]

    for t in tables:
        c.execute(t)

    conn.commit()
    conn.close()
    print(f"[DB] Inicializada ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")


def dia_actual():
    return date.today().isoformat()


def semana_actual():
    return datetime.now().strftime("%Y-W%W")


# ---- Bankroll ----

def registrar_bankroll(balance: float, nota: str = ""):
    p = placeholder(3)
    execute(
        f"INSERT INTO bankroll (timestamp, balance, nota) VALUES ({p})",
        (datetime.now().isoformat(), balance, nota)
    )


def get_balance_actual() -> float:
    rows = query("SELECT balance FROM bankroll ORDER BY id DESC LIMIT 1")
    return rows[0][0] if rows else 0.0


# ---- Apuestas ----

def registrar_apuesta(data: dict) -> int:
    p = placeholder(13)
    sql = f"""
        INSERT INTO apuestas
        (timestamp, fecha, sport, partido, mercado, seleccion, cuota,
         monto, confianza, razon, aprendizaje, resultado, semana)
        VALUES ({p})
        {'RETURNING id' if USE_POSTGRES else ''}
    """
    result = execute(sql, (
        datetime.now().isoformat(),
        dia_actual(),
        data["sport"], data["partido"], data["mercado"],
        data["seleccion"], data["cuota"], data["monto"],
        data["confianza"], data.get("razon",""),
        data.get("aprendizaje",""),
        "pendiente",
        semana_actual()
    ))
    if USE_POSTGRES:
        return result[0]
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM apuestas ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def actualizar_resultado(apuesta_id: int, resultado: str, ganancia: float):
    execute(
        f"UPDATE apuestas SET resultado={ph()}, ganancia={ph()} WHERE id={ph()}",
        (resultado, ganancia, apuesta_id)
    )


def get_apuestas_pendientes() -> list:
    rows = query("SELECT * FROM apuestas WHERE resultado = 'pendiente'")
    cols = ["id","timestamp","fecha","sport","partido","mercado","seleccion",
            "cuota","monto","confianza","razon","aprendizaje","resultado","ganancia","semana"]
    return [dict(zip(cols, r)) for r in rows]


def get_apuestas_del_dia(fecha: str = None) -> list:
    fecha = fecha or dia_actual()
    rows  = query(f"SELECT * FROM apuestas WHERE fecha = {ph()}", (fecha,))
    cols  = ["id","timestamp","fecha","sport","partido","mercado","seleccion",
             "cuota","monto","confianza","razon","aprendizaje","resultado","ganancia","semana"]
    return [dict(zip(cols, r)) for r in rows]


def get_roi_del_dia(fecha: str = None) -> dict:
    fecha    = fecha or dia_actual()
    apuestas = [a for a in get_apuestas_del_dia(fecha) if a["resultado"] != "pendiente"]
    invertido = sum(a["monto"] for a in apuestas)
    retorno   = sum(a["ganancia"] for a in apuestas)
    ganadas   = sum(1 for a in apuestas if a["resultado"] == "ganada")
    roi       = retorno / invertido if invertido > 0 else 0
    return {
        "fecha": fecha, "total": len(apuestas), "ganadas": ganadas,
        "invertido": round(invertido, 2), "retorno": round(retorno, 2),
        "roi": round(roi, 4), "pendientes": len(get_apuestas_del_dia(fecha)) - len(apuestas)
    }


# ---- Dias ----

def actualizar_dia(fecha: str = None):
    fecha = fecha or dia_actual()
    stats = get_roi_del_dia(fecha)
    if stats["total"] == 0:
        return
    roi_val   = stats["roi"]
    negativo  = 1 if roi_val < -0.05 else 0
    upsert = (
        f"""INSERT INTO dias (fecha, apuestas_total, apuestas_ganadas, invertido, retorno, roi, es_negativo)
            VALUES ({placeholder(7)})
            ON CONFLICT (fecha) DO UPDATE SET
                apuestas_total   = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.apuestas_total,
                apuestas_ganadas = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.apuestas_ganadas,
                invertido        = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.invertido,
                retorno          = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.retorno,
                roi              = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.roi,
                es_negativo      = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.es_negativo"""
    )
    execute(upsert, (fecha, stats["total"], stats["ganadas"],
                     stats["invertido"], stats["retorno"], roi_val, negativo))


def contar_dias_negativos_consecutivos() -> int:
    rows  = query("SELECT es_negativo FROM dias ORDER BY fecha DESC LIMIT 10")
    count = 0
    for (neg,) in rows:
        if neg == 1:
            count += 1
        else:
            break
    return count


# ---- Semanas ----

def actualizar_semana(semana: str):
    rows      = query(f"SELECT resultado, monto, ganancia FROM apuestas WHERE semana={ph()} AND resultado!='pendiente'", (semana,))
    total     = len(rows)
    ganadas   = sum(1 for r in rows if r[0]=="ganada")
    invertido = sum(r[1] for r in rows)
    retorno   = sum(r[2] for r in rows)
    roi       = retorno / invertido if invertido > 0 else 0
    negativa  = 1 if roi < -0.05 else 0
    upsert = (
        f"""INSERT INTO semanas (semana,apuestas_total,apuestas_ganadas,invertido,retorno,roi,es_negativa)
            VALUES ({placeholder(7)})
            ON CONFLICT (semana) DO UPDATE SET
                apuestas_total   = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.apuestas_total,
                apuestas_ganadas = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.apuestas_ganadas,
                invertido        = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.invertido,
                retorno          = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.retorno,
                roi              = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.roi,
                es_negativa      = {'EXCLUDED' if USE_POSTGRES else 'excluded'}.es_negativa"""
    )
    execute(upsert, (semana, total, ganadas, invertido, retorno, roi, negativa))


# ---- Stats globales ----

def get_stats_globales() -> dict:
    rows = query("SELECT COUNT(*), SUM(CASE WHEN resultado='ganada' THEN 1 ELSE 0 END), SUM(monto), SUM(ganancia) FROM apuestas WHERE resultado!='pendiente'")
    total, ganadas, invertido, retorno = rows[0]
    total     = total    or 0
    ganadas   = ganadas  or 0
    invertido = float(invertido or 0)
    retorno   = float(retorno   or 0)
    return {
        "total":     total,
        "ganadas":   ganadas,
        "winrate":   round(ganadas/total, 3) if total > 0 else 0,
        "invertido": round(invertido, 2),
        "retorno":   round(retorno, 2),
        "roi":       round(retorno/invertido, 3) if invertido else 0
    }


# ---- Estado ----

def set_estado(clave: str, valor: str):
    if USE_POSTGRES:
        execute("INSERT INTO estado_agente (clave,valor) VALUES (%s,%s) ON CONFLICT (clave) DO UPDATE SET valor=EXCLUDED.valor", (clave, valor))
    else:
        execute("INSERT OR REPLACE INTO estado_agente (clave,valor) VALUES (?,?)", (clave, valor))


def get_estado(clave: str, default=None):
    rows = query(f"SELECT valor FROM estado_agente WHERE clave={ph()}", (clave,))
    return rows[0][0] if rows else default
