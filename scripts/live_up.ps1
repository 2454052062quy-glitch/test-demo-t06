# Bật bản Live (cổng 3001/8001/5433, project t06-live). DỮ LIỆU THẬT.
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .env.live)) { Copy-Item .env.live.example .env.live; Write-Host "Đã tạo .env.live. Điền DB_PASSWORD, SECRET_KEY, thông tin POS365 rồi chạy lại."; exit 1 }
docker compose -p t06-live --env-file .env.live up -d --build
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" } | Select-Object -First 1).IPAddress
Write-Host "Trên máy này: http://localhost:3001"
if ($ip) { Write-Host "Trên điện thoại cùng Wi-Fi: http://${ip}:3001" }
