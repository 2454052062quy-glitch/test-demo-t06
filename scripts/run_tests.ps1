# Chạy toàn bộ test logic trên Windows (cần Python 3.12 + openpyxl).
Set-Location (Join-Path $PSScriptRoot "..")
python -m unittest discover -s backend/tests -t . -v
