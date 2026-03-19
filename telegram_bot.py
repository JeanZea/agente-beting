"""
Modulo de alertas por Telegram.
Notifica cada apuesta recomendada, reporte semanal y eventos criticos.
"""

import requests
from datetime import datetime

# --- Configuracion ---
TELEGRAM_TOKEN  = "8699628909:AAFneHEesYJuEoL4bM4upZ7ZJ0pqtfFr_Mo"     # de @BotFather
TELEGRAM_CHAT_ID = "1278761165"  # de @userinfobot

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def enviar_mensaje(texto: str, parse_mode: str = "HTML") -> bool:
    """Envia un mensaje al chat configurado."""
    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": texto,
                "parse_mode": parse_mode,
            },
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM] Error enviando mensaje: {e}")
        return False


def alerta_apuesta(analisis: dict, balance: float):
    """Notifica una apuesta recomendada."""
    emoji_riesgo = {"bajo": "🟢", "medio": "🟡", "alto": "🔴"}.get(analisis.get("riesgo", "medio"), "🟡")
    emoji_sport  = "⚽" if "soccer" in analisis.get("sport", "") else "🏀"

    texto = f"""
{emoji_sport} <b>APUESTA RECOMENDADA</b>

📋 <b>Partido:</b> {analisis["partido"]}
✅ <b>Apostar a:</b> {analisis["seleccion"]}
💰 <b>Cuota:</b> {analisis.get("cuota", 0)}
💵 <b>Monto:</b> ${analisis.get("monto", 0):.2f} ({analisis.get("pct_bankroll", 0)*100:.0f}% del bank)

📊 <b>Confianza:</b> {analisis.get("confianza", 0)*100:.0f}%
📈 <b>Value:</b> +{analisis.get("value", 0)*100:.1f}%
{emoji_riesgo} <b>Riesgo:</b> {analisis.get("riesgo", "medio").upper()}

📉 <b>Tendencia:</b> {analisis.get("tendencia", "")}
💡 <b>Razón:</b> {analisis.get("razon", "")}

🏦 <b>Bankroll actual:</b> ${balance:.2f}
🕐 {datetime.now().strftime("%d/%m/%Y %H:%M")}
"""
    return enviar_mensaje(texto.strip())


def alerta_sin_apuestas():
    """Notifica cuando no se encontraron apuestas con valor."""
    texto = "⏭ <b>Sin apuestas hoy</b>\n\nNo se encontraron partidos con valor suficiente. El agente espera el próximo ciclo."
    return enviar_mensaje(texto)


def alerta_reporte_semanal(semana: str, stats: dict, reporte_texto: str):
    """Envia el reporte semanal."""
    roi     = stats.get("roi", 0) * 100
    emoji   = "📈" if roi >= 0 else "📉"
    ganadas = stats.get("apuestas_ganadas", 0)
    total   = stats.get("apuestas_total", 0)
    wr      = round(ganadas / total * 100, 1) if total > 0 else 0

    texto = f"""
{emoji} <b>REPORTE SEMANAL — {semana}</b>

🎯 Apuestas: {ganadas}/{total} ganadas ({wr}% WR)
💵 Invertido: ${stats.get("invertido", 0):.2f}
💰 Retorno: ${stats.get("retorno", 0):.2f}
📊 ROI: {roi:+.1f}%

📝 <b>Análisis:</b>
{reporte_texto}
"""
    return enviar_mensaje(texto.strip())


def alerta_supervivencia(semanas_neg: int, limite: int):
    """Avisa cuando el agente está en zona de peligro."""
    restantes = limite - semanas_neg
    texto = f"""
⚠️ <b>ALERTA DE SUPERVIVENCIA</b>

El agente lleva <b>{semanas_neg} semana(s) consecutivas</b> con ROI negativo.
Quedan <b>{restantes} semana(s)</b> antes de la eliminación automática.

Considera revisar la estrategia.
"""
    return enviar_mensaje(texto.strip())


def alerta_eliminacion(stats: dict, balance: float):
    """Notifica la autoeliminación del agente."""
    texto = f"""
💀 <b>AGENTE ELIMINADO</b>

El agente superó el límite de semanas negativas consecutivas.

📊 <b>Stats finales:</b>
• Apuestas totales: {stats.get("total", 0)}
• Win rate: {stats.get("winrate", 0)*100:.1f}%
• ROI final: {stats.get("roi", 0)*100:.1f}%
• Capital final: ${balance:.2f}

El agente se ha detenido. Revisa el backup para análisis post-mortem.
"""
    return enviar_mensaje(texto.strip())


def alerta_inicio(balance: float, sports: list):
    """Mensaje de bienvenida al arrancar el agente."""
    deportes = "\n".join([f"  • {s}" for s in sports])
    texto = f"""
🤖 <b>AGENTE INICIADO</b>

🏦 Bankroll: ${balance:.2f}
⏰ Ciclos: 9:00 y 18:00 diariamente

🎮 <b>Deportes monitoreados:</b>
{deportes}

El agente está activo y buscando oportunidades.
"""
    return enviar_mensaje(texto.strip())


def test_conexion() -> bool:
    """Verifica que el bot funciona correctamente."""
    return enviar_mensaje("🟢 <b>Bot conectado correctamente.</b> El agente está listo.")
