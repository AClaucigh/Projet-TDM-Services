import json
import os
import pika
import requests
from io import BytesIO
from PIL import Image
from sklearn.cluster import KMeans
import numpy as np
import time

output_file = "/data/ville_images.json"

def wait_for_rabbitmq(host="rabbitmq", retries=10, delay=5, username="user", password="password"):
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, credentials=credentials)
    for i in range(retries):
        try:
            return pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError:
            print(f"[Processor] Tentative {i+1}/{retries} : RabbitMQ pas encore prêt, on attend {delay}s...")
            time.sleep(delay)
    raise Exception("[Processor] Impossible de se connecter à RabbitMQ après plusieurs tentatives.")

def get_dominant_colors(image_url, n_colors=3):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        image = image.resize((100, 100))  # Redimensionner pour accélérer KMeans
        image_array = np.array(image).reshape(-1, 3)

        kmeans = KMeans(n_clusters=n_colors, random_state=0)
        kmeans.fit(image_array)
        colors = kmeans.cluster_centers_.astype(int).tolist()
        return colors
    except Exception as e:
        print(f"[Processor] Erreur lors de l'analyse de l'image {image_url} : {e}")
        return []

def update_json_with_colors(ville, colors):
    try:
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []

        for item in data:
            if item["nom"] == ville["nom"] and item["pays"] == ville["pays"]:
                item["couleurs_dominantes"] = colors
                break

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[Processor] Fichier JSON mis à jour pour {ville['nom']}")
    except Exception as e:
        print(f"[Processor] Erreur lors de la mise à jour du fichier JSON : {e}")

def consume_queue():
    connection = wait_for_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue="ville_queue", durable=True)

    def callback(ch, method, properties, body):
        ville = json.loads(body)
        print(f"[Processor] Reçu : {ville['nom']}")
        colors = get_dominant_colors(ville["image"])
        update_json_with_colors(ville, colors)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue="ville_queue", on_message_callback=callback)
    print("[Processor] En attente de messages...")
    channel.start_consuming()

if __name__ == "__main__":
    print("[Processor] Démarrage du service...")
    consume_queue()