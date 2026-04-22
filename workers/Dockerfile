FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=redis://redis:6379
ENV ORCHESTRATOR_URL=http://orchestrator:8000

CMD ["python", "run_workers.py"]
