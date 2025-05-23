import json
import os
import pika
from PIL import Image
from sklearn.cluster import KMeans
import numpy as np
import time

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

def get_dominant_colors(image_path, n_colors=3):
    """Analyse une image locale et retourne les couleurs dominantes au format hexadécimal."""
    try:
        image = Image.open(image_path)
        image = image.resize((100, 100))  # Redimensionner pour accélérer KMeans
        image_array = np.array(image).reshape(-1, 3)

        kmeans = KMeans(n_clusters=n_colors, random_state=0)
        kmeans.fit(image_array)
        colors = kmeans.cluster_centers_.astype(int).tolist()

        # Convertir les couleurs en format hexadécimal
        hex_colors = ["#{:02x}{:02x}{:02x}".format(*color) for color in colors]
        return hex_colors
    except Exception as e:
        print(f"[Processor] Erreur lors de l'analyse de l'image {image_path} : {e}")
        return []

processed_images = set()

def update_metadata_file(ville, colors):
    """Met à jour le fichier ville_metadata.json avec les couleurs dominantes."""
    try:
        if os.path.exists("/data/ville_metadata.json"):
            with open("/data/ville_metadata.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []

        # Vérifier si la ville existe déjà dans le fichier
        updated = False
        for item in data:
            if item["nom"] == ville["nom"] and item["pays"] == ville["pays"]:
                item["couleurs_dominantes"] = colors
                updated = True
                break

        if not updated:
            ville["couleurs_dominantes"] = colors
            data.append(ville)

        # Sauvegarder les données mises à jour
        with open("/data/ville_metadata.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[Processor] Fichier ville_metadata.json mis à jour pour {ville['nom']}")
    except Exception as e:
        print(f"[Processor] Erreur lors de la mise à jour du fichier ville_metadata.json : {e}")

def publish_to_queue(ville, colors):
    """Publie les données enrichies dans RabbitMQ et met à jour le fichier ville_metadata.json."""
    if ville["image"] not in processed_images:
        try:
            # Mettre à jour le fichier ville_metadata.json
            update_metadata_file(ville, colors)

            # Publier les données dans RabbitMQ
            connection = wait_for_rabbitmq()
            channel = connection.channel()
            channel.queue_declare(queue="processed_images_queue", durable=True)

            ville["couleurs_dominantes"] = colors
            message = json.dumps(ville)
            channel.basic_publish(
                exchange="",
                routing_key="processed_images_queue",
                body=message,
                properties=pika.BasicProperties(delivery_mode=2)
            )
            processed_images.add(ville["image"])
            print(f"[Processor] Données publiées dans la file : {ville['nom']}")
            connection.close()
        except Exception as e:
            print(f"[Processor] Erreur lors de la publication dans RabbitMQ : {e}")

def consume_queue():
    """Consomme les messages de la file RabbitMQ et traite les images."""
    connection = wait_for_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue="ville_queue", durable=True)

    def callback(ch, method, properties, body):
        ville = json.loads(body)
        print(f"[Processor] Reçu : {ville['nom']}")

        # Utiliser le chemin local de l'image pour analyser les couleurs
        image_path = ville["image"]
        if os.path.exists(image_path):
            colors = get_dominant_colors(image_path)
            publish_to_queue(ville, colors)  # Publier les données enrichies
        else:
            print(f"[Processor] Image introuvable : {image_path}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue="ville_queue", on_message_callback=callback)
    print("[Processor] En attente de messages...")
    channel.start_consuming()

if __name__ == "__main__":
    print("[Processor] Démarrage du service...")
    consume_queue()