# ============================================================
#  SPORTS BETTING AGENT - CONFIG
#  En local: edita los valores directamente
#  En Railway: configura como variables de entorno
# ============================================================

import os

# --- APIs ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "sk-ant-XXXXXXX")
ODDS_API_KEY      = os.environ.get("ODDS_API_KEY",      "XXXXXXX")

# --- Telegram ---
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN",    "XXXXXXX")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID",  "XXXXXXX")

# --- Bankroll ---
BANKROLL_INICIAL  = float(os.environ.get("BANKROLL_INICIAL", "300.0"))

# --- Deportes a monitorear ---
SPORTS = [
    "basketball_nba",
    "basketball_ncaab",
    "basketball_euroleague",
    "basketball_nbl",
    "basketball_wncaab",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league",
    "soccer_conmebol_copa_libertadores",
]

REGIONS = "eu"

# --- Apuestas dinamicas ---
APUESTA_MINIMA_USD = 10.0
APUESTA_MAXIMA_PCT = 0.50
MIN_CONFIANZA      = 0.62
MIN_APUESTAS_DIA   = 3

# --- Logica de supervivencia ---
SEMANAS_NEGATIVAS_LIMITE = 3
ROI_MINIMO_SEMANAL       = -0.05

# --- Rutas ---
DB_PATH  = os.environ.get("DB_PATH",  "agent.db")
LOG_PATH = os.environ.get("LOG_PATH", "agent.log")
