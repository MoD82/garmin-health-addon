#!/usr/bin/env bash
set -e

exec python3 -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8099 \
    --log-level info
