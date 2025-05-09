import json
import os
import pika
import time
import requests
from SPARQLWrapper import SPARQLWrapper, JSON

print("[Collector] Démarrage du collecteur de données...")

output_file = "/data/ville_metadata.json"
image_folder = "/data/images"

def wait_for_rabbitmq(host="rabbitmq", retries=10, delay=5, username="user", password="password"):
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(host, credentials=credentials)
    for i in range(retries):
        try:
            return pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Collector] Tentative {i+1}/{retries} : RabbitMQ pas encore prêt, on attend {delay}s...")
            time.sleep(delay)
    raise Exception("[Collector] Impossible de se connecter à RabbitMQ après plusieurs tentatives.")

def download_image(image_url, folder=image_folder):
    """Télécharge une image et la stocke localement."""
    try:
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, os.path.basename(image_url))
        if not os.path.exists(filename):  # Éviter de retélécharger si l'image existe déjà
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Collector/1.0; +https://example.com)"}
            response = requests.get(image_url, headers=headers, stream=True)
            response.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"[Collector] Image téléchargée : {filename}")
        else:
            print(f"[Collector] Image déjà existante : {filename}")
        return filename
    except Exception as e:
        print(f"[Collector] Erreur lors du téléchargement de l'image {image_url} : {e}")
        return None

def collect_data():
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery("""
    SELECT DISTINCT ?villeLabel ?image ?paysLabel ?population ?superficie ?coordonnees ?fuseauHoraireLabel WHERE { 
      ?ville wdt:P31 wd:Q515;  # Sélectionne les villes
             wdt:P18 ?image;  # Image de la ville
             wdt:P17 ?pays;  # Pays de la ville
             wdt:P1082 ?population;  # Population
             wdt:P2046 ?superficie;  # Superficie
             wdt:P625 ?coordonnees;  # Coordonnées GPS
             wdt:P421 ?fuseauHoraire.  # Fuseau horaire

      SERVICE wikibase:label { 
        bd:serviceParam wikibase:language "fr". 
        ?ville rdfs:label ?villeLabel.  
        ?pays rdfs:label ?paysLabel.  
        ?fuseauHoraire rdfs:label ?fuseauHoraireLabel.  
      }
    }
    LIMIT 200
    """)
    sparql.setReturnFormat(JSON)

    # Ajouter un User-Agent personnalisé
    sparql.addCustomHttpHeader("User-Agent", "MyCollector/1.0 (https://example.com; contact@example.com)")

    results = sparql.query().convert()
    villes = []
    for result in results["results"]["bindings"]:
        ville = {
            "nom": result["villeLabel"]["value"],
            "pays": result["paysLabel"]["value"],
            "image": result["image"]["value"],
            "population": int(result["population"]["value"]),
            "superficie": float(result["superficie"]["value"]),
            "coordonnees": result["coordonnees"]["value"],
            "fuseau_horaire": result["fuseauHoraireLabel"]["value"]
        }

        # Télécharger l'image et mettre à jour le chemin local
        local_image_path = download_image(ville["image"])
        if local_image_path:
            ville["image"] = local_image_path
        else:
            print(f"[Collector] Image non disponible pour {ville['nom']} ({ville['pays']})")

        villes.append(ville)

    # Sauvegarde locale dans le volume partagé
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(villes, f, indent=2, ensure_ascii=False)
        print(f"[Collector] Données enregistrées dans {output_file}")

    return villes

def send_to_queue(villes):
    connection = wait_for_rabbitmq()
    channel = connection.channel()
    channel.queue_declare(queue="ville_queue", durable=True)

    for ville in villes:
        message = json.dumps(ville)
        channel.basic_publish(
            exchange="",
            routing_key="ville_queue",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f"[Collector] Envoyé : {ville['nom']}")
    connection.close()

if __name__ == "__main__":
    villes = collect_data()
    send_to_queue(villes)