# Bật bản Demo (cổng 3000/8000/5432). Chạy từ thư mục gốc dự án.
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Đã tạo .env từ .env.example. Hãy sửa DB_PASSWORD rồi chạy lại." ; exit 1 }
docker compose up -d --build
Write-Host "Mở http://localhost:3000"
