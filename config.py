import os
from dotenv import load_dotenv
load_dotenv()

# --- APIs ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "XXXXXXX")
ODDS_API_KEY      = os.environ.get("ODDS_API_KEY",      "XXXXXXX")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN",    "XXXXXXX")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID",  "XXXXXXX")

# --- Bankroll ---
BANKROLL_INICIAL  = float(os.environ.get("BANKROLL_INICIAL", "300.0"))

# --- Deportes (solo futbol y basketball) ---
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

# --- Mercados habilitados (sin límite) ---
MARKETS = "h2h,spreads,totals"   # h2h + handicap + over/under

REGIONS = "eu"

# --- Apuestas dinámicas ---
APUESTA_MINIMA_USD  = 5.0
APUESTA_MAXIMA_PCT  = 0.60    # hasta 60% del bankroll si confianza muy alta
MIN_CONFIANZA       = 0.62
MIN_APUESTAS_DIA    = 3

# --- Evaluación DIARIA de ROI (nuevo) ---
DIAS_NEGATIVOS_LIMITE = 5      # 5 días negativos consecutivos → eliminación
ROI_MINIMO_DIARIO     = -0.05  # -5% ROI diario = día negativo

# --- Aprendizaje intra-día ---
MAX_APUESTAS_DIA      = 15     # máximo de apuestas por día
OBJETIVO_ROI_DIARIO   = 0.10   # el agente busca terminar el día con +10% ROI

# --- Rutas ---
DB_PATH  = os.environ.get("DB_PATH",  "agent.db")
LOG_PATH = os.environ.get("LOG_PATH", "agent.log")
