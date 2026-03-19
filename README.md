# 🏀 Sports Betting Agent

Agente autónomo de análisis de apuestas deportivas con lógica de supervivencia.
Usa Claude API como cerebro y The-Odds-API para datos en tiempo real.

---

## Estructura

```
sports_agent/
├── config.py          ← EDITA ESTO PRIMERO
├── database.py        ← SQLite (memoria del agente)
├── data_fetcher.py    ← Obtiene partidos y cuotas
├── agent.py           ← Cerebro Claude (análisis + decisiones)
├── main.py            ← Loop autónomo + scheduler
└── requirements.txt
```

---

## Setup (10 minutos)

### 1. Instalar dependencias
```bash
cd sports_agent
pip install -r requirements.txt
```

### 2. Conseguir las APIs (ambas gratuitas para empezar)

**Claude API**
- Ir a: https://console.anthropic.com
- Crear API key
- Pegar en `config.py` → `ANTHROPIC_API_KEY`

**The-Odds-API** (500 requests/mes gratis)
- Ir a: https://the-odds-api.com
- Registrarse (gratis)
- Pegar API key en `config.py` → `ODDS_API_KEY`

### 3. Configurar bankroll
En `config.py`:
```python
BANKROLL_INICIAL  = 300.0    # tu capital en USD
APUESTA_UNITARIA  = 0.02     # 2% por apuesta (recomendado)
MIN_CONFIANZA     = 0.62     # umbral mínimo para apostar
```

### 4. Correr el agente
```bash
python main.py
```

---

## Lógica de supervivencia

El agente se **autoeliminá** si pierde 3 semanas consecutivas con ROI < -5%.

Al eliminarse:
- Hace backup de la base de datos
- Registra stats finales en el log
- Borra su configuración
- Se detiene

Esto evita perder todo el capital con una estrategia que no funciona.

---

## Cómo registrar resultados

Los resultados de las apuestas debes registrarlos manualmente en la DB:

```python
from database import actualizar_resultado

# id de la apuesta, "ganada"/"perdida"/"void", ganancia neta en USD
actualizar_resultado(1, "ganada", 15.30)
actualizar_resultado(2, "perdida", -10.00)
```

En futuras versiones esto se puede automatizar con scraping de resultados.

---

## Deploy autónomo (Railway)

Para que corra 24/7 sin tu computadora:

1. Crear cuenta en https://railway.app (gratis)
2. Conectar el repo
3. Configurar variables de entorno (API keys)
4. Deploy → el agente corre solo

---

## Roadmap

- [ ] Auto-registro de resultados (scraping)
- [ ] Más deportes (soccer, tenis)
- [ ] Dashboard web de estadísticas
- [ ] Integración con Telegram para alertas
- [ ] Backtesting con datos históricos
