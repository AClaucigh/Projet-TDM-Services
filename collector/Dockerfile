# collector/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY collector.py .

RUN pip install --no-cache-dir SPARQLWrapper pika

CMD ["python", "collector.py"]
