import requests
from config import ODDS_API_KEY, SPORTS, REGIONS, MARKETS

BASE_URL = "https://api.the-odds-api.com/v4"


def get_partidos_del_dia(sport: str) -> list:
    url    = f"{BASE_URL}/sports/{sport}/odds"
    params = {
        "apiKey":      ODDS_API_KEY,
        "regions":     REGIONS,
        "markets":     MARKETS,
        "oddsFormat":  "decimal",
        "dateFormat":  "iso",
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        partidos = []
        for evento in resp.json():
            mercados = _extraer_mercados(evento)
            if not mercados:
                continue
            partidos.append({
                "id":       evento["id"],
                "sport":    sport,
                "partido":  f"{evento['home_team']} vs {evento['away_team']}",
                "home":     evento["home_team"],
                "away":     evento["away_team"],
                "commence": evento["commence_time"],
                "mercados": mercados,
                # mantener cuotas h2h para compatibilidad
                "cuotas":   mercados.get("h2h", {}),
            })
        return partidos
    except Exception as e:
        print(f"[FETCHER] Error {sport}: {e}")
        return []


def _extraer_mercados(evento: dict) -> dict:
    """Extrae las mejores cuotas por mercado (h2h, spreads, totals)."""
    resultado = {}
    for bookmaker in evento.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            key = market["key"]
            if key not in resultado:
                resultado[key] = {}
            for outcome in market["outcomes"]:
                nombre = outcome["name"]
                precio = outcome["price"]
                punto  = outcome.get("point", "")
                label  = f"{nombre} {punto}".strip() if punto else nombre
                if label not in resultado[key] or precio > resultado[key][label]:
                    resultado[key][label] = precio
    return resultado


def get_todos_los_partidos() -> list:
    todos = []
    for sport in SPORTS:
        partidos = get_partidos_del_dia(sport)
        todos.extend(partidos)
        print(f"[FETCHER] {sport}: {len(partidos)} partidos")
    return todos
