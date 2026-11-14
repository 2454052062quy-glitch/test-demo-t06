FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Mã đặt ở /srv/backend để import "backend.app..." (cùng cách chạy test)
COPY . /srv/backend
RUN mkdir -p /app/uploads /app/data
ENV UPLOAD_DIR=/app/uploads DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
