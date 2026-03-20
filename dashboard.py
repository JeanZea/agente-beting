import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import (
    get_conn, get_stats_globales, get_balance_actual,
    actualizar_resultado, registrar_bankroll,
    contar_dias_negativos_consecutivos, init_db
)
from config import BANKROLL_INICIAL, DIAS_NEGATIVOS_LIMITE

app = Flask(__name__)
CORS(app)
DIR = os.path.dirname(os.path.abspath(__file__))

# Init DB al arrancar el dashboard
init_db()


def query(sql, params=()):
    """Ejecuta una query y retorna todas las filas."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows


@app.route("/")
def index():
    return send_from_directory(DIR, "dashboard.html")


@app.route("/api/stats")
def stats():
    globales    = get_stats_globales()
    balance     = get_balance_actual()
    semanas_neg = contar_dias_negativos_consecutivos()
    return jsonify({
        **globales,
        "balance":           balance,
        "bankroll_inicial":  BANKROLL_INICIAL,
        "pnl":               round(balance - BANKROLL_INICIAL, 2),
        "dias_negativos": semanas_neg,
        "dias_limite":    SEMANAS_NEGATIVAS_LIMITE,
        "vidas_restantes": DIAS_NEGATIVOS_LIMITE - semanas_neg,
    })


@app.route("/api/apuestas")
def apuestas():
    rows = query("""
        SELECT id, timestamp, sport, partido, seleccion, cuota,
               monto, confianza, resultado, ganancia, semana, razon
        FROM apuestas ORDER BY id DESC LIMIT 100
    """)
    cols = ["id","timestamp","sport","partido","seleccion","cuota",
            "monto","confianza","resultado","ganancia","semana","razon"]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.route("/api/semanas")
def semanas():
    rows = query("""
        SELECT semana, apuestas_total, apuestas_ganadas,
               invertido, retorno, roi, es_negativa
        FROM semanas ORDER BY semana DESC LIMIT 20
    """)
    cols = ["semana","apuestas_total","apuestas_ganadas",
            "invertido","retorno","roi","es_negativa"]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.route("/api/bankroll")
def bankroll():
    rows = query("SELECT timestamp, balance, nota FROM bankroll ORDER BY id ASC")
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
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
