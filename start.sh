#!/bin/bash
if [ "$SERVICE" = "dashboard" ]; then
    echo "Iniciando Dashboard..."
    gunicorn dashboard:app --bind 0.0.0.0:$PORT
else
    echo "Iniciando Agente..."
    python main.py
fi
