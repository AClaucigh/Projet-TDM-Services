FROM python:3.11-slim

WORKDIR /app

# Copier le script et les fichiers nécessaires
COPY collector.py .
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "collector.py"]