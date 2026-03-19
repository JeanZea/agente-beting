import anthropic
import json
from datetime import datetime
from config import (
    ANTHROPIC_API_KEY, MIN_CONFIANZA, MIN_APUESTAS_DIA,
    APUESTA_MINIMA_USD, APUESTA_MAXIMA_PCT
)
from database import get_balance_actual, get_stats_globales

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """Eres un agente experto en apuestas deportivas de basketball y futbol.
Tu objetivo es maximizar el ROI usando value betting y analisis de tendencias.

DEPORTES QUE MANEJAS:
- Basketball: NBA, NCAA, Euroleague, NBL
- Futbol: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Copa Libertadores

COMO CALCULAR EL MONTO A APOSTAR:
- confianza >= 0.80 (favorito claro, gran valor en cuota): sugiere 30-50% del bankroll
- confianza >= 0.70 (bastante seguro): sugiere 15-25% del bankroll
- confianza >= 0.62 (razonablemente seguro): sugiere 5-10% del bankroll
- confianza < 0.62: NO apostar

ANALISIS PARA BASKETBALL:
- Racha reciente del equipo (ultimos 5-10 partidos)
- Ventaja de local vs visitante
- Contexto: playoffs, temporada regular, importancia del partido
- Lesiones de jugadores clave si las conoces

ANALISIS PARA FUTBOL:
- Forma reciente (ultimos 5 partidos)
- Posicion en la tabla y motivacion
- H2H historico entre los equipos
- Local vs visitante (el local tiene gran ventaja en futbol)
- Fase de la competicion (eliminatorias vs fase de grupos)
- En futbol considera tambien el empate como resultado posible

REGLAS GENERALES:
1. Calcula probabilidad implicita: 1/cuota
2. Solo apuesta si tu estimacion supera la implicita en 5%+
3. Sé honesto: si no tienes suficiente informacion, NO apostar
4. En futbol el empate es comun, tenlo en cuenta

Responde SOLO con este JSON exacto:
{
  "apostar": true/false,
  "seleccion": "nombre del equipo o resultado",
  "mercado": "h2h",
  "cuota": 1.85,
  "confianza": 0.75,
  "pct_bankroll": 0.25,
  "probabilidad_estimada": 0.72,
  "probabilidad_implicita": 0.54,
  "value": 0.18,
  "tendencia": "descripcion breve de la tendencia del equipo seleccionado",
  "razon": "razon concreta y especifica para apostar o no",
  "riesgo": "bajo/medio/alto"
}
"""


def calcular_monto(confianza: float, pct_sugerido: float, balance: float) -> float:
    """Calcula el monto real a apostar con límites de seguridad."""
    monto = balance * min(pct_sugerido, APUESTA_MAXIMA_PCT)
    monto = max(monto, APUESTA_MINIMA_USD)
    monto = min(monto, balance * APUESTA_MAXIMA_PCT)
    return round(monto, 2)


def analizar_partido(partido: dict, umbral_override: float = None) -> dict:
    """Analiza un partido y decide si apostar y cuánto."""
    balance  = get_balance_actual()
    stats    = get_stats_globales()
    umbral   = umbral_override or MIN_CONFIANZA

    cuotas_str = "\n".join([
        f"  - {equipo}: {cuota} (prob. implícita: {round(1/cuota*100,1)}%)"
        for equipo, cuota in partido["cuotas"].items()
    ])

    prompt = f"""
PARTIDO: {partido["partido"]}
DEPORTE: {partido["sport"]}
HORA UTC: {partido["commence"]}

CUOTAS DISPONIBLES:
{cuotas_str}

ESTADO DEL AGENTE:
- Bankroll actual: ${balance:.2f}
- Win rate histórico: {stats["winrate"]*100:.1f}% ({stats["total"]} apuestas)
- ROI acumulado: {stats["roi"]*100:.1f}%

Analiza usando tu conocimiento de basketball:
- ¿Cuál equipo tiene ventaja real?
- ¿Hay value en las cuotas?
- ¿Cuál es la tendencia reciente de cada equipo?
- ¿Cuánto % del bankroll merece esta apuesta?

Umbral mínimo de confianza para apostar: {umbral:.0%}
Responde SOLO con el JSON.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        analisis = json.loads(raw.strip())
        analisis["partido"] = partido["partido"]
        analisis["sport"]   = partido["sport"]

        # Filtrar por umbral de confianza
        if analisis.get("confianza", 0) < umbral:
            analisis["apostar"] = False
            analisis["razon"]   = f"Confianza {analisis.get('confianza',0):.0%} < umbral {umbral:.0%}. " + analisis.get("razon","")
            analisis["monto"]   = 0
        else:
            pct = analisis.get("pct_bankroll", 0.05)
            analisis["monto"] = calcular_monto(analisis["confianza"], pct, balance)

        return analisis

    except Exception as e:
        print(f"[AGENT] Error analizando {partido['partido']}: {e}")
        return {"apostar": False, "razon": str(e), "partido": partido["partido"], "monto": 0}


def analizar_partidos_con_minimo(partidos: list) -> list:
    """
    Analiza todos los partidos garantizando mínimo MIN_APUESTAS_DIA apuestas.
    Si no llega al mínimo, baja el umbral de confianza a 0.55.
    """
    # Primera pasada con umbral normal
    resultados = [analizar_partido(p) for p in partidos]
    apuestas   = [r for r in resultados if r.get("apostar")]

    # Si no llega al mínimo, segunda pasada con umbral reducido
    if len(apuestas) < MIN_APUESTAS_DIA:
        print(f"[AGENT] Solo {len(apuestas)} apuestas encontradas. Bajando umbral a 0.55...")
        no_apostados = [p for p, r in zip(partidos, resultados) if not r.get("apostar")]
        for partido in no_apostados:
            if len(apuestas) >= MIN_APUESTAS_DIA:
                break
            analisis = analizar_partido(partido, umbral_override=0.55)
            if analisis.get("apostar"):
                apuestas.append(analisis)
                resultados.append(analisis)

    return resultados


def generar_reporte_semanal(semana: str, stats_semana: dict) -> str:
    prompt = f"""
Genera un reporte ejecutivo breve (máximo 150 palabras) de esta semana de apuestas:

Semana: {semana}
Apuestas: {stats_semana.get('apuestas_total', 0)} | Ganadas: {stats_semana.get('apuestas_ganadas', 0)}
Invertido: ${stats_semana.get('invertido', 0):.2f} | Retorno: ${stats_semana.get('retorno', 0):.2f}
ROI: {stats_semana.get('roi', 0)*100:.1f}%

Incluye: qué funcionó, qué no, y 1 ajuste concreto para la próxima semana.
"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Error generando reporte: {e}"


def decidir_supervivencia(semanas_negativas: int, limite: int) -> dict:
    if semanas_negativas >= limite:
        return {
            "continuar": False,
            "mensaje": f"PROTOCOLO DE ELIMINACION ACTIVADO\n"
                       f"El agente registro {semanas_negativas} semanas consecutivas negativas.\n"
                       f"Eliminando configuracion y deteniendo operaciones..."
        }
    restantes = limite - semanas_negativas
    return {
        "continuar": True,
        "mensaje": f"Agente operativo. Margen: {restantes} semana(s) antes de eliminacion."
    }
