"""
SPORTS BETTING AGENT — Loop autónomo con evaluación diaria y aprendizaje
"""

import schedule
import time
import logging
import os
import shutil
from datetime import datetime

from config import (
    BANKROLL_INICIAL, DIAS_NEGATIVOS_LIMITE,
    DB_PATH, LOG_PATH, MIN_APUESTAS_DIA, SPORTS,
    MAX_APUESTAS_DIA, OBJETIVO_ROI_DIARIO
)
from database import (
    init_db, registrar_bankroll, get_balance_actual,
    registrar_apuesta, dia_actual, semana_actual,
    contar_dias_negativos_consecutivos, actualizar_dia,
    actualizar_semana, get_stats_globales, set_estado,
    get_roi_del_dia, get_apuestas_del_dia
)
from data_fetcher import get_todos_los_partidos
from agent import analizar_partidos_con_minimo, generar_reporte_diario, decidir_supervivencia
from results_checker import verificar_y_registrar
from telegram_bot import (
    alerta_apuesta, alerta_sin_apuestas, alerta_reporte_semanal,
    alerta_supervivencia, alerta_eliminacion, alerta_inicio,
    test_conexion, enviar_mensaje
)

os.makedirs(os.path.dirname(LOG_PATH) if os.path.dirname(LOG_PATH) else ".", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)


def ciclo_resultados():
    """Verifica resultados pendientes y actualiza stats del día."""
    log.info("Verificando resultados pendientes...")
    resueltas = verificar_y_registrar()
    if resueltas > 0:
        actualizar_dia()
        actualizar_semana(semana_actual())
        roi_dia = get_roi_del_dia()
        balance = get_balance_actual()
        enviar_mensaje(
            f"🔄 <b>AUTO-RESULTADOS</b>\n\n"
            f"{resueltas} apuesta(s) actualizadas.\n"
            f"📊 ROI hoy: <b>{roi_dia['roi']*100:+.1f}%</b>\n"
            f"🏦 Bankroll: <b>${balance:.2f}</b>"
        )
    return resueltas


def ciclo_analisis():
    log.info("=" * 60)
    log.info("  CICLO DE ANALISIS")
    log.info("=" * 60)

    # 1. Verificar resultados primero
    ciclo_resultados()

    # 2. Verificar supervivencia DIARIA
    dias_neg = contar_dias_negativos_consecutivos()
    decision = decidir_supervivencia(dias_neg, DIAS_NEGATIVOS_LIMITE)
    log.info(decision["mensaje"])

    if dias_neg >= 1:
        alerta_supervivencia(dias_neg, DIAS_NEGATIVOS_LIMITE)

    if not decision["continuar"]:
        protocolo_eliminacion()
        return

    # 3. Verificar límite de apuestas del día
    apuestas_hoy = get_apuestas_del_dia()
    if len(apuestas_hoy) >= MAX_APUESTAS_DIA:
        log.info(f"Límite diario alcanzado ({MAX_APUESTAS_DIA} apuestas). Esperando mañana.")
        return

    # 4. Verificar si ya se alcanzó el objetivo de ROI del día
    roi_dia = get_roi_del_dia()
    if roi_dia["roi"] >= OBJETIVO_ROI_DIARIO and roi_dia["total"] >= MIN_APUESTAS_DIA:
        log.info(f"Objetivo ROI del día alcanzado: {roi_dia['roi']*100:+.1f}%. Descansando.")
        enviar_mensaje(f"🎯 <b>Objetivo del día alcanzado!</b>\nROI: {roi_dia['roi']*100:+.1f}%\nEl agente descansa hasta mañana.")
        return

    # 5. Obtener partidos
    log.info("Obteniendo partidos...")
    partidos = get_todos_los_partidos()
    if not partidos:
        log.warning("Sin partidos disponibles.")
        alerta_sin_apuestas()
        return
    log.info(f"{len(partidos)} partidos encontrados.")

    # 6. Filtrar partidos ya analizados hoy
    partidos_analizados = set(a["partido"] for a in apuestas_hoy)
    partidos_nuevos = [p for p in partidos if p["partido"] not in partidos_analizados]
    log.info(f"{len(partidos_nuevos)} partidos nuevos para analizar.")

    if not partidos_nuevos:
        log.info("Todos los partidos ya fueron analizados hoy.")
        return

    # 7. Analizar con aprendizaje intra-día
    log.info(f"ROI actual del día: {roi_dia['roi']*100:+.1f}% | Objetivo: +{OBJETIVO_ROI_DIARIO*100:.0f}%")
    resultados = analizar_partidos_con_minimo(partidos_nuevos)

    # 8. Registrar y notificar
    balance = get_balance_actual()
    registradas = 0

    for analisis in resultados:
        if len(get_apuestas_del_dia()) >= MAX_APUESTAS_DIA:
            log.info("Límite diario alcanzado durante el ciclo.")
            break

        if analisis.get("apostar"):
            log.info(f"\n  ✅ APOSTAR → {analisis['seleccion']}")
            log.info(f"  Partido:    {analisis['partido']}")
            log.info(f"  Mercado:    {analisis.get('mercado','h2h')} | Cuota: {analisis.get('cuota',0)}")
            log.info(f"  Confianza:  {analisis.get('confianza',0)*100:.0f}% | Monto: ${analisis.get('monto',0):.2f}")
            log.info(f"  Aprendizaje:{analisis.get('aprendizaje','')[:100]}")

            registrar_apuesta({
                "sport":       analisis["sport"],
                "partido":     analisis["partido"],
                "mercado":     analisis.get("mercado","h2h"),
                "seleccion":   analisis["seleccion"],
                "cuota":       analisis.get("cuota", 0),
                "monto":       analisis.get("monto", 0),
                "confianza":   analisis.get("confianza", 0),
                "razon":       analisis.get("razon",""),
                "aprendizaje": analisis.get("aprendizaje",""),
            })

            alerta_apuesta(analisis, balance)
            registradas += 1
        else:
            log.info(f"  ⏭  PASAR → {analisis['partido']} | {analisis.get('razon','')[:80]}")

    if registradas == 0:
        alerta_sin_apuestas()

    # 9. Stats del ciclo
    roi_actualizado = get_roi_del_dia()
    stats = get_stats_globales()
    log.info(f"\nResumen: {registradas} apuestas este ciclo.")
    log.info(f"ROI hoy: {roi_actualizado['roi']*100:+.1f}% | WR global: {stats['winrate']*100:.1f}% | ROI global: {stats['roi']*100:.1f}%")


def reporte_diario():
    """Reporte al final del día."""
    fecha    = dia_actual()
    actualizar_dia(fecha)
    roi_dia  = get_roi_del_dia(fecha)

    if roi_dia["total"] == 0:
        return

    reporte  = generar_reporte_diario(fecha, roi_dia)
    balance  = get_balance_actual()
    emoji    = "📈" if roi_dia["roi"] >= 0 else "📉"

    log.info(f"\nREPORTE DIARIO {fecha}:\n{reporte}")

    enviar_mensaje(
        f"{emoji} <b>REPORTE DIARIO — {fecha}</b>\n\n"
        f"🎯 {roi_dia['ganadas']}/{roi_dia['total']} ganadas\n"
        f"💵 Invertido: ${roi_dia['invertido']:.2f}\n"
        f"💰 Retorno: ${roi_dia['retorno']:+.2f}\n"
        f"📊 ROI: {roi_dia['roi']*100:+.1f}%\n"
        f"🏦 Bankroll: ${balance:.2f}\n\n"
        f"📝 {reporte}"
    )


def protocolo_eliminacion():
    stats   = get_stats_globales()
    balance = get_balance_actual()
    log.critical("=" * 60)
    log.critical("  PROTOCOLO DE ELIMINACION ACTIVADO")
    log.critical(f"  ROI final: {stats['roi']*100:.1f}% | Balance: ${balance:.2f}")
    log.critical("=" * 60)
    alerta_eliminacion(stats, balance)
    if os.path.exists(DB_PATH):
        backup = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(DB_PATH, backup)
        os.remove(DB_PATH)
    exit(0)


def setup():
    log.info("Inicializando agente...")
    init_db()
    balance = get_balance_actual()
    if balance == 0.0:
        registrar_bankroll(BANKROLL_INICIAL, "Deposito inicial")
        log.info(f"Bankroll inicial: ${BANKROLL_INICIAL:.2f}")
    else:
        log.info(f"Bankroll actual: ${balance:.2f}")
    set_estado("inicio", datetime.now().isoformat())
    if test_conexion():
        alerta_inicio(get_balance_actual(), SPORTS)
    log.info("Agente listo.")


if __name__ == "__main__":
    setup()

    # Análisis cada 3 horas (más frecuente para buscar valor durante el día)
    schedule.every(3).hours.do(ciclo_analisis)

    # Verificar resultados cada hora
    schedule.every(1).hours.do(ciclo_resultados)

    # Reporte diario a las 11pm
    schedule.every().day.at("23:00").do(reporte_diario)

    log.info("Ejecutando primer ciclo...")
    ciclo_analisis()

    log.info("\nScheduler: análisis cada 3h | resultados cada 1h | reporte 23:00\n")
    while True:
        schedule.run_pending()
        time.sleep(60)
