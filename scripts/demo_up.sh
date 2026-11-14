#!/usr/bin/env sh
# Bật bản Demo (cổng 3000/8000/5432). Chạy từ thư mục gốc dự án.
set -e
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Đã tạo .env từ .env.example."
fi
docker compose up -d --build
echo "Đã khởi động hệ thống T06 Demo tại: http://localhost:3000"
