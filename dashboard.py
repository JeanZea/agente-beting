"""
Dashboard API — Flask server
Correr: python dashboard.py  (puerto 5000)
Abrir:  http://127.0.0.1:5000
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import (
    get_conn, get_stats_globales, get_balance_actual,
    actualizar_resultado, registrar_bankroll,
    contar_semanas_negativas_consecutivas
)
from config import BANKROLL_INICIAL, SEMANAS_NEGATIVAS_LIMITE

app  = Flask(__name__)
CORS(app)

DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return send_from_directory(DIR, "dashboard.html")


@app.route("/api/stats")
def stats():
    globales    = get_stats_globales()
    balance     = get_balance_actual()
    semanas_neg = contar_semanas_negativas_consecutivas()
    return jsonify({
        **globales,
        "balance":           balance,
        "bankroll_inicial":  BANKROLL_INICIAL,
        "pnl":               round(balance - BANKROLL_INICIAL, 2),
        "semanas_negativas": semanas_neg,
        "semanas_limite":    SEMANAS_NEGATIVAS_LIMITE,
        "vidas_restantes":   SEMANAS_NEGATIVAS_LIMITE - semanas_neg,
    })


@app.route("/api/apuestas")
def apuestas():
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, timestamp, sport, partido, seleccion, cuota,
               monto, confianza, resultado, ganancia, semana, razon
        FROM apuestas ORDER BY id DESC LIMIT 100
    """).fetchall()
    conn.close()
    cols = ["id","timestamp","sport","partido","seleccion","cuota",
            "monto","confianza","resultado","ganancia","semana","razon"]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.route("/api/semanas")
def semanas():
    conn = get_conn()
    rows = conn.execute("""
        SELECT semana, apuestas_total, apuestas_ganadas,
               invertido, retorno, roi, es_negativa
        FROM semanas ORDER BY semana DESC LIMIT 20
    """).fetchall()
    conn.close()
    cols = ["semana","apuestas_total","apuestas_ganadas",
            "invertido","retorno","roi","es_negativa"]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.route("/api/bankroll")
def bankroll():
    conn = get_conn()
    rows = conn.execute(
        "SELECT timestamp, balance, nota FROM bankroll ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return jsonify([{"timestamp": r[0], "balance": r[1], "nota": r[2]} for r in rows])


@app.route("/api/resultado", methods=["POST"])
def guardar_resultado():
    data       = request.json
    apuesta_id = data["id"]
    resultado  = data["resultado"]
    ganancia   = float(data["ganancia"])

    actualizar_resultado(apuesta_id, resultado, ganancia)

    balance_nuevo = round(get_balance_actual() + ganancia, 2)
    registrar_bankroll(balance_nuevo, f"Resultado apuesta #{apuesta_id}: {resultado}")

    return jsonify({"ok": True, "balance": balance_nuevo})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
