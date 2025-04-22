FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y python3-tk && \
    pip install --no-cache-dir -r requirements.txt

CMD ["python", "recommender.py"]