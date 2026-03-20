import anthropic
import json
from datetime import datetime
from config import (
    ANTHROPIC_API_KEY, MIN_CONFIANZA, MIN_APUESTAS_DIA,
    APUESTA_MINIMA_USD, APUESTA_MAXIMA_PCT, OBJETIVO_ROI_DIARIO
)
from database import get_balance_actual, get_stats_globales, get_roi_del_dia, get_apuestas_del_dia

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Eres un agente experto en apuestas deportivas de basketball y fútbol.
Tu misión es terminar CADA DÍA con ROI positivo haciendo apuestas inteligentes y aprendiendo de cada resultado.

MERCADOS DISPONIBLES:
- h2h: resultado final (1X2 en fútbol, 1/2 en basketball)
- spreads: handicap de puntos/goles
- totals: over/under de puntos/goles totales

DEPORTES: Basketball (NBA, NCAA, Euroleague) y Fútbol (Premier, La Liga, Serie A, Bundesliga, Ligue 1, Champions, Copa Libertadores)

ESTRATEGIA DE APUESTA DINÁMICA:
- confianza >= 0.85: apuesta 40-60% del bankroll (muy alta convicción)
- confianza >= 0.75: apuesta 20-35% del bankroll
- confianza >= 0.65: apuesta 10-20% del bankroll
- confianza >= 0.62: apuesta 5-10% del bankroll
- confianza < 0.62: NO apostar

APRENDIZAJE INTRA-DÍA:
- Recibirás el historial de apuestas del día actual con sus resultados
- Analiza qué patrones funcionaron y cuáles fallaron
- Si vas perdiendo en el día → sé más selectivo, busca valor real
- Si vas ganando → mantén la estrategia, no te sobreexpandas
- Ajusta el tipo de mercado según el deporte y el contexto

ANÁLISIS POR DEPORTE:
Basketball: ritmo del juego, racha reciente, back-to-back games, lesiones, ventaja local
Fútbol: forma últimos 5, posición en tabla, H2H, motivación (descenso/Champions), local siempre fuerte

REGLA DE ORO: Solo apuesta si ves valor REAL. Probabilidad estimada > probabilidad implícita de la cuota en 5%+.

Responde SOLO con este JSON:
{
  "apostar": true/false,
  "seleccion": "nombre exacto del resultado",
  "mercado": "h2h|spreads|totals",
  "cuota": 1.85,
  "confianza": 0.75,
  "pct_bankroll": 0.25,
  "probabilidad_estimada": 0.72,
  "probabilidad_implicita": 0.54,
  "value": 0.18,
  "tendencia": "descripcion breve",
  "aprendizaje": "que aprendiste del historial del dia para esta decision",
  "razon": "razon concreta y especifica",
  "riesgo": "bajo|medio|alto"
}
"""


def formatear_historial_dia(apuestas_dia: list) -> str:
    """Formatea el historial del día para dárselo al agente como contexto."""
    if not apuestas_dia:
        return "Sin apuestas previas hoy."

    resueltas  = [a for a in apuestas_dia if a["resultado"] != "pendiente"]
    pendientes = [a for a in apuestas_dia if a["resultado"] == "pendiente"]

    roi_dia    = get_roi_del_dia()
    lines      = [f"HISTORIAL DE HOY ({roi_dia['fecha']}):"]
    lines.append(f"ROI del día: {roi_dia['roi']*100:+.1f}% | Invertido: ${roi_dia['invertido']:.2f} | Retorno: ${roi_dia['retorno']:+.2f}")
    lines.append(f"Resueltas: {roi_dia['ganadas']}/{roi_dia['total']} ganadas | Pendientes: {roi_dia['pendientes']}")
    lines.append("")

    for a in resueltas[-5:]:  # últimas 5 resueltas
        emoji = "✅" if a["resultado"] == "ganada" else "❌"
        lines.append(f"{emoji} {a['partido']} → {a['seleccion']} ({a['mercado']}) @ {a['cuota']} | {'+'if a['ganancia']>0 else ''}${a['ganancia']:.2f}")

    if pendientes:
        lines.append(f"\nPendientes de resultado: {len(pendientes)} apuesta(s)")

    return "\n".join(lines)


def calcular_monto(pct_sugerido: float, balance: float) -> float:
    monto = balance * min(pct_sugerido, APUESTA_MAXIMA_PCT)
    monto = max(monto, APUESTA_MINIMA_USD)
    monto = min(monto, balance * APUESTA_MAXIMA_PCT)
    return round(monto, 2)


def formatear_mercados(partido: dict) -> str:
    """Formatea todos los mercados disponibles del partido."""
    lines = []
    for mercado_key, opciones in partido.get("mercados", {}).items():
        nombre_mercado = {"h2h": "Resultado final", "spreads": "Handicap", "totals": "Over/Under"}.get(mercado_key, mercado_key)
        lines.append(f"\n  [{nombre_mercado}]")
        for opcion, cuota in opciones.items():
            prob = round(1/cuota*100, 1) if cuota > 0 else 0
            lines.append(f"    - {opcion}: {cuota} (prob. implícita: {prob}%)")
    return "\n".join(lines)


def analizar_partido(partido: dict, historial_dia: list, umbral: float = None) -> dict:
    umbral  = umbral or MIN_CONFIANZA
    balance = get_balance_actual()
    stats   = get_stats_globales()
    roi_dia = get_roi_del_dia()

    historial_str  = formatear_historial_dia(historial_dia)
    mercados_str   = formatear_mercados(partido)
    objetivo_resto = OBJETIVO_ROI_DIARIO - roi_dia["roi"]

    prompt = f"""
{historial_str}

---
PARTIDO A ANALIZAR:
Deporte: {partido["sport"]}
Partido: {partido["partido"]}
Hora UTC: {partido["commence"]}

MERCADOS DISPONIBLES:
{mercados_str}

ESTADO ACTUAL:
- Bankroll: ${balance:.2f}
- ROI de hoy: {roi_dia["roi"]*100:+.1f}%
- Objetivo ROI restante para hoy: {objetivo_resto*100:+.1f}%
- Win rate histórico: {stats["winrate"]*100:.1f}% ({stats["total"]} apuestas)
- ROI histórico: {stats["roi"]*100:.1f}%

Umbral mínimo de confianza: {umbral:.0%}

Analiza el partido considerando:
1. El historial de hoy (qué está funcionando, qué no)
2. Todos los mercados disponibles (no solo h2h)
3. Si necesitas recuperar ROI o mantenerlo
4. El valor real en las cuotas

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

        if analisis.get("confianza", 0) < umbral:
            analisis["apostar"] = False
            analisis["razon"]   = f"Confianza {analisis.get('confianza',0):.0%} < umbral {umbral:.0%}. " + analisis.get("razon","")
            analisis["monto"]   = 0
        else:
            analisis["monto"] = calcular_monto(analisis.get("pct_bankroll", 0.05), balance)

        return analisis

    except Exception as e:
        print(f"[AGENT] Error: {e}")
        return {"apostar": False, "razon": str(e), "partido": partido["partido"], "monto": 0, "sport": partido["sport"]}


def analizar_partidos_con_minimo(partidos: list) -> list:
    """Analiza partidos pasando el historial del día a cada análisis."""
    resultados = []
    apuestas_ok = 0

    for partido in partidos:
        # Historial actualizado antes de cada análisis
        historial_dia = get_apuestas_del_dia()
        analisis = analizar_partido(partido, historial_dia)
        resultados.append(analisis)
        if analisis.get("apostar"):
            apuestas_ok += 1

    # Si no llega al mínimo, segunda pasada con umbral reducido
    if apuestas_ok < MIN_APUESTAS_DIA:
        print(f"[AGENT] Solo {apuestas_ok} apuestas. Bajando umbral a 0.55...")
        for partido in partidos:
            if apuestas_ok >= MIN_APUESTAS_DIA:
                break
            ya_analizado = any(r["partido"] == partido["partido"] and r.get("apostar") for r in resultados)
            if ya_analizado:
                continue
            historial_dia = get_apuestas_del_dia()
            analisis = analizar_partido(partido, historial_dia, umbral=0.55)
            if analisis.get("apostar"):
                resultados.append(analisis)
                apuestas_ok += 1

    return resultados


def generar_reporte_diario(fecha: str, stats_dia: dict) -> str:
    roi = stats_dia.get("roi", 0) * 100
    prompt = f"""
Genera un reporte ejecutivo brevísimo (máximo 100 palabras) del día de apuestas:

Fecha: {fecha}
Apuestas: {stats_dia.get('total',0)} | Ganadas: {stats_dia.get('ganadas',0)}
Invertido: ${stats_dia.get('invertido',0):.2f} | Retorno: ${stats_dia.get('retorno',0):.2f}
ROI: {roi:+.1f}%

Incluye: qué funcionó, qué mercados/deportes dieron mejor resultado, y 1 ajuste para mañana.
"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Error: {e}"


def decidir_supervivencia(dias_negativos: int, limite: int) -> dict:
    if dias_negativos >= limite:
        return {
            "continuar": False,
            "mensaje": f"PROTOCOLO DE ELIMINACION: {dias_negativos} dias negativos consecutivos."
        }
    return {
        "continuar": True,
        "mensaje": f"Agente operativo. {limite - dias_negativos} dia(s) de margen."
    }
