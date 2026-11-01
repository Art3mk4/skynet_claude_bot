#!/bin/bash
set -e

# set -e: падение pytest прерывает скрипт и бот не стартует
echo "Running tests..."
TEST_MODE=1 python -m pytest -v --tb=short
echo "✓ All tests passed"

echo "Starting bot..."
exec python main.py
