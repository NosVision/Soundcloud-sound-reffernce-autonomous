FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces ใช้ 7860, host อื่นส่ง PORT มาเอง
ENV PORT=7860
EXPOSE 7860

CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
