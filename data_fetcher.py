import requests
import json
from datetime import datetime
from config import ODDS_API_KEY, SPORTS, REGIONS


BASE_URL = "https://api.the-odds-api.com/v4"


def get_partidos_del_dia(sport: str) -> list:
    """
    Obtiene los partidos de hoy con sus cuotas.
    Retorna lista de dicts con info del partido.
    """
    url = f"{BASE_URL}/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": "h2h",         # head to head (1X2)
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        partidos = []
        for evento in data:
            cuotas = _extraer_cuotas(evento)
            if not cuotas:
                continue
            partidos.append({
                "id":           evento["id"],
                "sport":        sport,
                "partido":      f"{evento['home_team']} vs {evento['away_team']}",
                "home":         evento["home_team"],
                "away":         evento["away_team"],
                "commence":     evento["commence_time"],
                "cuotas":       cuotas,
            })
        return partidos
    except Exception as e:
        print(f"[FETCHER] Error obteniendo partidos de {sport}: {e}")
        return []


def _extraer_cuotas(evento: dict) -> dict:
    """Extrae las mejores cuotas disponibles de todos los bookmakers."""
    mejores = {}
    for bookmaker in evento.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    nombre = outcome["name"]
                    precio = outcome["price"]
                    if nombre not in mejores or precio > mejores[nombre]:
                        mejores[nombre] = precio
    return mejores


def get_todos_los_partidos() -> list:
    """Obtiene partidos de todos los deportes configurados."""
    todos = []
    for sport in SPORTS:
        partidos = get_partidos_del_dia(sport)
        todos.extend(partidos)
        print(f"[FETCHER] {sport}: {len(partidos)} partidos encontrados")
    return todos


def get_sports_disponibles() -> list:
    """Lista todos los deportes disponibles en la API."""
    url = f"{BASE_URL}/sports"
    params = {"apiKey": ODDS_API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[FETCHER] Error: {e}")
        return []


def get_stats_equipo_mock(equipo: str) -> dict:
    """
    Placeholder para estadísticas del equipo.
    En producción: conectar a API-Sports o scraping de Basketball-Reference.
    """
    return {
        "equipo": equipo,
        "nota": "Stats detalladas requieren API-Sports ($)",
        "fuente": "mock"
    }
