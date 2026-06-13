#!/bin/bash
echo "========================================"
echo " Weisse Wunderstern"
echo " Text Report Analysis Service"
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
