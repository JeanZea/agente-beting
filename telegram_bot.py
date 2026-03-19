"""
Modulo de alertas por Telegram.
Lee token y chat_id desde config.py (o variables de entorno en Railway).
"""

import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def enviar_mensaje(texto: str, parse_mode: str = "HTML") -> bool:
    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": parse_mode},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")
        return False


def alerta_apuesta(analisis: dict, balance: float):
    emoji_riesgo = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}.get(analisis.get("riesgo","medio"), "🟡")
    emoji_sport  = "⚽" if "soccer" in analisis.get("sport","") else "🏀"
    texto = f"""{emoji_sport} <b>APUESTA RECOMENDADA</b>

📋 <b>Partido:</b> {analisis["partido"]}
✅ <b>Apostar a:</b> {analisis["seleccion"]}
💰 <b>Cuota:</b> {analisis.get("cuota",0)}
💵 <b>Monto:</b> ${analisis.get("monto",0):.2f} ({analisis.get("pct_bankroll",0)*100:.0f}% del bank)

📊 <b>Confianza:</b> {analisis.get("confianza",0)*100:.0f}%
📈 <b>Value:</b> +{analisis.get("value",0)*100:.1f}%
{emoji_riesgo} <b>Riesgo:</b> {analisis.get("riesgo","medio").upper()}

📉 <b>Tendencia:</b> {analisis.get("tendencia","")}
💡 <b>Razón:</b> {analisis.get("razon","")}

🏦 <b>Bankroll:</b> ${balance:.2f}
🕐 {datetime.now().strftime("%d/%m/%Y %H:%M")}"""
    return enviar_mensaje(texto.strip())


def alerta_sin_apuestas():
    return enviar_mensaje("⏭ <b>Sin apuestas hoy</b>\n\nNo se encontraron partidos con valor suficiente.")


def alerta_reporte_semanal(semana: str, stats: dict, reporte_texto: str):
    roi   = stats.get("roi", 0) * 100
    emoji = "📈" if roi >= 0 else "📉"
    total = stats.get("apuestas_total", 0)
    gan   = stats.get("apuestas_ganadas", 0)
    wr    = round(gan / total * 100, 1) if total > 0 else 0
    texto = f"""{emoji} <b>REPORTE SEMANAL — {semana}</b>

🎯 {gan}/{total} ganadas ({wr}% WR)
💵 Invertido: ${stats.get("invertido",0):.2f}
💰 Retorno: ${stats.get("retorno",0):.2f}
📊 ROI: {roi:+.1f}%

📝 <b>Análisis:</b>
{reporte_texto}"""
    return enviar_mensaje(texto.strip())


def alerta_supervivencia(semanas_neg: int, limite: int):
    restantes = limite - semanas_neg
    return enviar_mensaje(
        f"⚠️ <b>ALERTA DE SUPERVIVENCIA</b>\n\n"
        f"El agente lleva <b>{semanas_neg} semana(s)</b> con ROI negativo.\n"
        f"Quedan <b>{restantes} semana(s)</b> antes de eliminación."
    )


def alerta_eliminacion(stats: dict, balance: float):
    return enviar_mensaje(
        f"💀 <b>AGENTE ELIMINADO</b>\n\n"
        f"• Win rate: {stats.get('winrate',0)*100:.1f}%\n"
        f"• ROI final: {stats.get('roi',0)*100:.1f}%\n"
        f"• Capital final: ${balance:.2f}\n\n"
        f"El agente se ha detenido. Revisa el backup."
    )


def alerta_inicio(balance: float, sports: list):
    deportes = "\n".join([f"  • {s}" for s in sports])
    return enviar_mensaje(
        f"🤖 <b>AGENTE INICIADO</b>\n\n"
        f"🏦 Bankroll: ${balance:.2f}\n"
        f"⏰ Ciclos: 9:00 y 18:00\n\n"
        f"🎮 <b>Deportes:</b>\n{deportes}"
    )


def test_conexion() -> bool:
    return enviar_mensaje("🟢 <b>Bot conectado correctamente.</b> El agente está listo.")
