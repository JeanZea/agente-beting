# ============================================================
#  SPORTS BETTING AGENT - CONFIG
# ============================================================

# --- APIs ---
ANTHROPIC_API_KEY = "XXXXXX"       # console.anthropic.com
ODDS_API_KEY      = "XXXXXX"               # the-odds-api.com

# --- Bankroll ---
BANKROLL_INICIAL  = 300.0    # en USD (~1000 soles)

# --- Deportes a monitorear ---
SPORTS = [
    # Basketball
    "basketball_nba",
    "basketball_ncaab",
    "basketball_euroleague",
    "basketball_nbl",
    "basketball_wncaab",
    # Futbol
    "soccer_epl",               # Premier League
    "soccer_spain_la_liga",     # La Liga
    "soccer_italy_serie_a",     # Serie A
    "soccer_germany_bundesliga",# Bundesliga
    "soccer_france_ligue_one",  # Ligue 1
    "soccer_uefa_champs_league",# Champions League
    "soccer_conmebol_copa_libertadores", # Copa Libertadores
]

# --- Regiones de odds ---
REGIONS = "eu"   # eu | us | uk | au

# --- Apuestas dinamicas ---
# La IA decide el % segun su confianza:
#   confianza >= 0.80 -> hasta 50% del bankroll
#   confianza >= 0.70 -> hasta 25% del bankroll
#   confianza >= 0.62 -> hasta 10% del bankroll
APUESTA_MINIMA_USD = 10.0    # minimo en USD por apuesta
APUESTA_MAXIMA_PCT = 0.50    # techo absoluto: 50% del bankroll
MIN_CONFIANZA      = 0.62    # umbral base
MIN_APUESTAS_DIA   = 3       # si no llega a 3, baja umbral a 0.55

# --- Logica de supervivencia ---
SEMANAS_NEGATIVAS_LIMITE = 3
ROI_MINIMO_SEMANAL       = -0.05

# --- Rutas ---
DB_PATH  = "agent.db"
LOG_PATH = "agent.log"
