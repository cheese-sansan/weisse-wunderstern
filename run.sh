#!/bin/bash
echo "========================================"
echo " Lite Agent Orchestrator"
echo " Academic Distillation Engine"
echo "========================================"
echo " MODE: ${MODE:-cli}"
echo "========================================"

if [ "$MODE" = "api" ]; then
    echo "Starting API server on port ${API_PORT:-8000}..."
    exec python main_api.py
else
    echo "Running CLI pipeline..."
    exec python main.py "$@"
fi
