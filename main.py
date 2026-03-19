"""
=============================================================
  SPORTS BETTING AGENT
  Loop autonomo con logica de supervivencia + Telegram
=============================================================
  Correr:  python main.py
  Detener: Ctrl+C
=============================================================
"""

import schedule
import time
import logging
import os
import shutil
from datetime import datetime

from config import (
    BANKROLL_INICIAL, SEMANAS_NEGATIVAS_LIMITE,
    DB_PATH, LOG_PATH, MIN_APUESTAS_DIA, SPORTS
)
from database import (
    init_db, registrar_bankroll, get_balance_actual,
    registrar_apuesta, semana_actual,
    contar_semanas_negativas_consecutivas,
    actualizar_semana, get_stats_globales, set_estado
)
from data_fetcher import get_todos_los_partidos
from agent import analizar_partidos_con_minimo, generar_reporte_semanal, decidir_supervivencia
from results_checker import verificar_y_registrar
from telegram_bot import (
    alerta_apuesta, alerta_sin_apuestas, alerta_reporte_semanal,
    alerta_supervivencia, alerta_eliminacion, alerta_inicio,
    test_conexion, enviar_mensaje
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def ciclo_resultados():
    """Verifica resultados de apuestas pendientes y notifica por Telegram."""
    log.info("Verificando resultados de apuestas pendientes...")
    resueltas = verificar_y_registrar()

    if resueltas > 0:
        stats   = get_stats_globales()
        balance = get_balance_actual()
        enviar_mensaje(
            f"🔄 <b>AUTO-RESULTADOS</b>\n\n"
            f"{resueltas} apuesta(s) actualizadas automáticamente.\n"
            f"🏦 Bankroll actual: <b>${balance:.2f}</b>\n"
            f"📊 ROI total: <b>{stats['roi']*100:+.1f}%</b>"
        )


def ciclo_analisis():
    log.info("=" * 60)
    log.info("  INICIO DE CICLO DE ANALISIS")
    log.info("=" * 60)

    # 1. Primero verificar resultados pendientes
    ciclo_resultados()

    # 2. Verificar supervivencia
    semanas_neg = contar_semanas_negativas_consecutivas()
    decision    = decidir_supervivencia(semanas_neg, SEMANAS_NEGATIVAS_LIMITE)
    log.info(decision["mensaje"])

    if semanas_neg >= 1:
        alerta_supervivencia(semanas_neg, SEMANAS_NEGATIVAS_LIMITE)

    if not decision["continuar"]:
        protocolo_eliminacion()
        return

    # 3. Obtener partidos
    log.info("Obteniendo partidos del dia...")
    partidos = get_todos_los_partidos()
    if not partidos:
        log.warning("No se encontraron partidos.")
        alerta_sin_apuestas()
        return
    log.info(f"{len(partidos)} partidos encontrados.")

    # 4. Analizar
    log.info(f"Analizando (minimo {MIN_APUESTAS_DIA} apuestas)...")
    resultados = analizar_partidos_con_minimo(partidos)

    # 5. Procesar y notificar
    balance = get_balance_actual()
    apuestas_registradas = 0

    for analisis in resultados:
        if analisis.get("apostar"):
            log.info(f"\n  APOSTAR -> {analisis['seleccion']} | {analisis['partido']}")
            log.info(f"  Cuota: {analisis.get('cuota')} | Confianza: {analisis.get('confianza',0)*100:.0f}% | Monto: ${analisis.get('monto',0):.2f}")

            registrar_apuesta({
                "sport":     analisis["sport"],
                "partido":   analisis["partido"],
                "mercado":   analisis.get("mercado", "h2h"),
                "seleccion": analisis["seleccion"],
                "cuota":     analisis.get("cuota", 0),
                "monto":     analisis.get("monto", 0),
                "confianza": analisis.get("confianza", 0),
                "razon":     f"[{analisis.get('pct_bankroll',0)*100:.0f}% bank | value:{analisis.get('value',0):.2f}] {analisis.get('razon','')}",
            })

            alerta_apuesta(analisis, balance)
            apuestas_registradas += 1
        else:
            log.info(f"  PASAR -> {analisis['partido']} | {analisis.get('razon','')[:80]}")

    if apuestas_registradas == 0:
        alerta_sin_apuestas()

    stats = get_stats_globales()
    log.info(f"\nResumen: {apuestas_registradas} apuestas hoy.")
    log.info(f"Stats -> WR: {stats['winrate']*100:.1f}% | ROI: {stats['roi']*100:.1f}% | Total: {stats['total']}")


def reporte_semanal():
    semana = semana_actual()
    log.info(f"\nGENERANDO REPORTE SEMANAL: {semana}")
    actualizar_semana(semana)

    from database import get_conn
    conn = get_conn()
    row  = conn.execute("SELECT * FROM semanas WHERE semana = ?", (semana,)).fetchone()
    conn.close()

    if not row:
        log.info("Sin datos esta semana.")
        return

    cols = ["semana","apuestas_total","apuestas_ganadas","invertido","retorno","roi","es_negativa"]
    stats_semana = dict(zip(cols, row))
    reporte      = generar_reporte_semanal(semana, stats_semana)

    log.info(f"\n{reporte}\n")
    with open(f"reporte_{semana}.txt", "w") as f:
        f.write(reporte)

    alerta_reporte_semanal(semana, stats_semana, reporte)


def protocolo_eliminacion():
    stats   = get_stats_globales()
    balance = get_balance_actual()

    log.critical("=" * 60)
    log.critical("  PROTOCOLO DE ELIMINACION ACTIVADO")
    log.critical(f"  Win rate: {stats['winrate']*100:.1f}% | ROI: {stats['roi']*100:.1f}%")
    log.critical(f"  Capital final: ${balance:.2f}")
    log.critical("=" * 60)

    alerta_eliminacion(stats, balance)

    if os.path.exists(DB_PATH):
        backup = f"backup_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(DB_PATH, backup)
        os.remove(DB_PATH)
        log.critical(f"  DB respaldada en: {backup}")

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
        log.info("Telegram OK.")
        alerta_inicio(get_balance_actual(), SPORTS)
    else:
        log.warning("Telegram no conectado.")

    log.info("Agente listo.")


if __name__ == "__main__":
    setup()

    # Análisis 2x por día
    schedule.every().day.at("09:00").do(ciclo_analisis)
    schedule.every().day.at("18:00").do(ciclo_analisis)

    # Verificar resultados cada 2 horas
    schedule.every(2).hours.do(ciclo_resultados)

    # Reporte semanal cada lunes
    schedule.every().monday.at("08:00").do(reporte_semanal)

    log.info("Ejecutando primer ciclo...")
    ciclo_analisis()

    log.info("\nScheduler activo. Ctrl+C para detener.\n")
    while True:
        schedule.run_pending()
        time.sleep(60)
