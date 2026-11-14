#!/usr/bin/env sh
# Chạy toàn bộ test logic (chỉ cần Python 3.12 + openpyxl; không cần Docker/Postgres/FastAPI).
set -e
cd "$(dirname "$0")/.."
python3 -m unittest discover -s backend/tests -t . -v
