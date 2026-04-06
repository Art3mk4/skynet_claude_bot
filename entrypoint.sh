#!/bin/bash
set -e

echo "Running tests..."
python -m pytest -v --tb=short

if [ $? -eq 0 ]; then
    echo "✓ All tests passed"
    echo "Starting bot..."
    exec python main.py
else
    echo "✗ Tests failed, not starting bot"
    exit 1
fi
