import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Crea las tablas si no existen."""
    conn = get_conn()
    c = conn.cursor()

    # Bankroll histórico
    c.execute("""
        CREATE TABLE IF NOT EXISTS bankroll (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            balance   REAL    NOT NULL,
            nota      TEXT
        )
    """)

    # Cada apuesta recomendada
    c.execute("""
        CREATE TABLE IF NOT EXISTS apuestas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            sport           TEXT    NOT NULL,
            partido         TEXT    NOT NULL,
            mercado         TEXT    NOT NULL,
            seleccion       TEXT    NOT NULL,
            cuota           REAL    NOT NULL,
            monto           REAL    NOT NULL,
            confianza       REAL    NOT NULL,
            razon           TEXT,
            resultado       TEXT    DEFAULT 'pendiente',  -- pendiente | ganada | perdida | void
            ganancia        REAL    DEFAULT 0.0,
            semana          TEXT    NOT NULL
        )
    """)

    # Resumen semanal
    c.execute("""
        CREATE TABLE IF NOT EXISTS semanas (
            semana          TEXT    PRIMARY KEY,
            apuestas_total  INTEGER DEFAULT 0,
            apuestas_ganadas INTEGER DEFAULT 0,
            invertido       REAL    DEFAULT 0.0,
            retorno         REAL    DEFAULT 0.0,
            roi             REAL    DEFAULT 0.0,
            es_negativa     INTEGER DEFAULT 0
        )
    """)

    # Estado del agente
    c.execute("""
        CREATE TABLE IF NOT EXISTS estado_agente (
            clave   TEXT PRIMARY KEY,
            valor   TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Base de datos inicializada.")


def semana_actual():
    return datetime.now().strftime("%Y-W%W")


# ---- Bankroll ----

def registrar_bankroll(balance: float, nota: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO bankroll (timestamp, balance, nota) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), balance, nota)
    )
    conn.commit()
    conn.close()


def get_balance_actual() -> float:
    conn = get_conn()
    row = conn.execute(
        "SELECT balance FROM bankroll ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else 0.0


# ---- Apuestas ----

def registrar_apuesta(data: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO apuestas
        (timestamp, sport, partido, mercado, seleccion, cuota, monto, confianza, razon, semana)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        data["sport"], data["partido"], data["mercado"],
        data["seleccion"], data["cuota"], data["monto"],
        data["confianza"], data.get("razon", ""), semana_actual()
    ))
    apuesta_id = c.lastrowid
    conn.commit()
    conn.close()
    return apuesta_id


def actualizar_resultado(apuesta_id: int, resultado: str, ganancia: float):
    conn = get_conn()
    conn.execute(
        "UPDATE apuestas SET resultado = ?, ganancia = ? WHERE id = ?",
        (resultado, ganancia, apuesta_id)
    )
    conn.commit()
    conn.close()


def get_apuestas_pendientes() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM apuestas WHERE resultado = 'pendiente'"
    ).fetchall()
    conn.close()
    cols = ["id","timestamp","sport","partido","mercado","seleccion",
            "cuota","monto","confianza","razon","resultado","ganancia","semana"]
    return [dict(zip(cols, r)) for r in rows]


# ---- Semanas ----

def actualizar_semana(semana: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT resultado, monto, ganancia FROM apuestas WHERE semana = ? AND resultado != 'pendiente'",
        (semana,)
    ).fetchall()

    total       = len(rows)
    ganadas     = sum(1 for r in rows if r[0] == "ganada")
    invertido   = sum(r[1] for r in rows)
    retorno     = sum(r[2] for r in rows)
    roi         = (retorno / invertido) if invertido > 0 else 0.0
    negativa    = 1 if roi < -0.05 else 0

    conn.execute("""
        INSERT INTO semanas (semana, apuestas_total, apuestas_ganadas, invertido, retorno, roi, es_negativa)
        VALUES (?, ?, ?, ?, ?, ?, ?)
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
    rows = conn.execute(
        "SELECT es_negativa FROM semanas ORDER BY semana DESC LIMIT 5"
    ).fetchall()
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
    row = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN resultado='ganada' THEN 1 ELSE 0 END) as ganadas,
            SUM(monto) as invertido,
            SUM(ganancia) as retorno
        FROM apuestas WHERE resultado != 'pendiente'
    """).fetchone()
    conn.close()
    total, ganadas, invertido, retorno = row
    total     = total or 0
    ganadas   = ganadas or 0
    invertido = invertido or 0.0
    retorno   = retorno or 0.0
    return {
        "total": total,
        "ganadas": ganadas,
        "winrate": round(ganadas / total, 3) if total > 0 else 0,
        "invertido": round(invertido, 2),
        "retorno": round(retorno, 2),
        "roi": round(retorno / invertido, 3) if invertido > 0 else 0
    }


# ---- Estado del agente ----

def set_estado(clave: str, valor: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO estado_agente (clave, valor) VALUES (?, ?)",
        (clave, valor)
    )
    conn.commit()
    conn.close()


def get_estado(clave: str, default=None) -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT valor FROM estado_agente WHERE clave = ?", (clave,)
    ).fetchone()
    conn.close()
    return row[0] if row else default
