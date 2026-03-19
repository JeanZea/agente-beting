"""
Auto-registro de resultados.
Consulta la Odds-API por scores completados,
hace match con apuestas pendientes y actualiza la BD.
"""

import requests
from datetime import datetime, timezone
from config import ODDS_API_KEY, SPORTS
from database import (
    get_apuestas_pendientes, actualizar_resultado,
    get_balance_actual, registrar_bankroll, actualizar_semana, semana_actual
)

BASE_URL = "https://api.the-odds-api.com/v4"


def get_scores_completados(sport: str) -> list:
    """Obtiene partidos completados de las últimas 48hs."""
    url = f"{BASE_URL}/sports/{sport}/scores"
    params = {
        "apiKey":       ODDS_API_KEY,
        "daysFrom":     2,     # últimas 48hs
        "dateFormat":   "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        # Solo los que ya terminaron
        return [g for g in resp.json() if g.get("completed")]
    except Exception as e:
        print(f"[RESULTS] Error obteniendo scores de {sport}: {e}")
        return []


def normalizar(texto: str) -> str:
    """Normaliza nombre de equipo para comparación."""
    return texto.lower().strip().replace("  ", " ")


def determinar_ganador(game: dict) -> str | None:
    """Extrae el equipo ganador de un partido completado."""
    scores = game.get("scores")
    if not scores or len(scores) < 2:
        return None
    try:
        equipos = {s["name"]: int(s["score"]) for s in scores}
        ganador = max(equipos, key=equipos.get)
        # Empate
        vals = list(equipos.values())
        if vals[0] == vals[1]:
            return "empate"
        return ganador
    except Exception:
        return None


def partido_coincide(apuesta_partido: str, game_home: str, game_away: str) -> bool:
    """Verifica si un juego de la API corresponde a la apuesta guardada."""
    ap = normalizar(apuesta_partido)
    home = normalizar(game_home)
    away = normalizar(game_away)
    return (home in ap or away in ap or
            home[:6] in ap or away[:6] in ap)


def verificar_y_registrar():
    """
    Ciclo principal: busca apuestas pendientes,
    intenta hacer match con resultados y actualiza.
    """
    pendientes = get_apuestas_pendientes()
    if not pendientes:
        print("[RESULTS] Sin apuestas pendientes.")
        return 0

    print(f"[RESULTS] {len(pendientes)} apuestas pendientes. Buscando resultados...")

    resueltas = 0

    # Obtener scores por deporte único
    sports_unicos = list(set(a["sport"] for a in pendientes))
    scores_por_sport = {}
    for sport in sports_unicos:
        scores_por_sport[sport] = get_scores_completados(sport)
        print(f"[RESULTS] {sport}: {len(scores_por_sport[sport])} partidos completados encontrados")

    # Hacer match
    for apuesta in pendientes:
        sport   = apuesta["sport"]
        scores  = scores_por_sport.get(sport, [])

        for game in scores:
            home = game.get("home_team", "")
            away = game.get("away_team", "")

            if not partido_coincide(apuesta["partido"], home, away):
                continue

            # Match encontrado
            ganador   = determinar_ganador(game)
            seleccion = normalizar(apuesta["seleccion"])

            if ganador is None:
                print(f"[RESULTS] Sin score válido para: {apuesta['partido']}")
                continue

            if ganador == "empate":
                # Verificar si apostó al empate
                if "empate" in seleccion or "draw" in seleccion or "x" == seleccion:
                    ganancia = round(apuesta["monto"] * (apuesta["cuota"] - 1), 2)
                    resultado = "ganada"
                else:
                    ganancia = -apuesta["monto"]
                    resultado = "perdida"
            elif normalizar(ganador) in seleccion or seleccion in normalizar(ganador):
                ganancia  = round(apuesta["monto"] * (apuesta["cuota"] - 1), 2)
                resultado = "ganada"
            else:
                ganancia  = -apuesta["monto"]
                resultado = "perdida"

            # Actualizar BD
            actualizar_resultado(apuesta["id"], resultado, ganancia)

            # Actualizar bankroll
            balance_nuevo = round(get_balance_actual() + ganancia, 2)
            registrar_bankroll(
                balance_nuevo,
                f"Auto-resultado apuesta #{apuesta['id']}: {resultado} ({apuesta['partido']})"
            )

            emoji = "✅" if resultado == "ganada" else "❌"
            print(f"[RESULTS] {emoji} {apuesta['partido']} → {apuesta['seleccion']} → {resultado.upper()} | "
                  f"{'+'if ganancia>0 else ''}${ganancia:.2f} | Nuevo balance: ${balance_nuevo:.2f}")

            resueltas += 1
            break  # siguiente apuesta

    # Actualizar stats semanales
    if resueltas > 0:
        actualizar_semana(semana_actual())

    print(f"[RESULTS] {resueltas} apuestas resueltas automáticamente.")
    return resueltas
