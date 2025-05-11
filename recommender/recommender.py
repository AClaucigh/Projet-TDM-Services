import json
import pika
import numpy as np
import streamlit as st
from sklearn.linear_model import Perceptron
from sklearn.preprocessing import StandardScaler
from PIL import Image
import os

USER_DATA_FILE = "/data/users.json"

# Charger les données utilisateur
def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "w") as f:
            json.dump({}, f)  # Crée un fichier JSON vide
        return {}
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

# Sauvegarder les données utilisateur
def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Consommer les messages de RabbitMQ
def consume_queue():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host="rabbitmq",
            credentials=pika.PlainCredentials("user", "password")
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue="processed_images_queue", durable=True)

    images_data = []

    while True:
        method_frame, properties, body = channel.basic_get(queue="processed_images_queue", auto_ack=True)
        if method_frame:
            ville = json.loads(body)
            # print(f"[Recommender] Message consommé : {ville}")  # Ajouter ce log au besoin 
            images_data.append(ville)
        else:
            break

    connection.close()
    return images_data

# Trier les images selon les préférences utilisateur
def sort_images_by_preferences(user_colors, images_features, images_paths):
    preferred_color_values = [int(c[1:], 16) for c in user_colors]
    distances = [min(abs(f[2] - pc) for pc in preferred_color_values) for f in images_features]
    sorted_indices = np.argsort(distances)
    return [images_paths[i] for i in sorted_indices]

# Interface Streamlit
def main():
    st.title("Recommandation d'Images")
    st.sidebar.title("Connexion / Inscription")

    # Charger les données utilisateur
    user_data = load_user_data()

    # Connexion / Inscription
    username = st.sidebar.text_input("Nom d'utilisateur")
    user_colors = st.sidebar.text_input("Couleurs préférées (ex: #ff0000, #00ff00)").split(",")

    if st.sidebar.button("Se connecter / S'inscrire"):
        if username:
            if username not in user_data:
                user_data[username] = {"colors": user_colors, "features": [], "labels": []}
                save_user_data(user_data)
            st.session_state["username"] = username
            st.session_state["user_colors"] = user_colors
            st.success(f"Bienvenue, {username} !")

    # Vérifier si l'utilisateur est connecté
    if "username" in st.session_state:
        username = st.session_state["username"]
        user_colors = st.session_state["user_colors"]

        # Charger les données des images depuis RabbitMQ une seule fois
        if "images_data" not in st.session_state:
            st.info("Chargement des données depuis RabbitMQ...")
            st.session_state["images_data"] = consume_queue()

        images_data = st.session_state["images_data"]

        if not images_data:
            st.error("Aucune donnée d'image disponible.")
            return

        # Extraire les caractéristiques des images
        features, images_paths = [], []
        for entry in images_data:
            couleurs_dominantes = [int(c[1:], 16) for c in entry["couleurs_dominantes"]]
            couleur_moyenne = np.mean(couleurs_dominantes)
            population = entry["population"]
            superficie = entry["superficie"]

            features.append([population, superficie, couleur_moyenne])
            images_paths.append(entry["image"])

        features = np.array(features)

        # Trier les images selon les préférences utilisateur
        sorted_images = sort_images_by_preferences(user_colors, features, images_paths)

        # Afficher les images triées
        if "current_index" not in st.session_state:
            st.session_state["current_index"] = 0

        if st.session_state["current_index"] < len(sorted_images):
            current_image_path = sorted_images[st.session_state["current_index"]]
            image = Image.open(current_image_path)
            st.image(image, caption=f"Image {st.session_state['current_index'] + 1}/{len(sorted_images)}", use_container_width=True)

            # Boutons Like / Dislike
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👍 Like"):
                    save_preference(user_data, username, features, images_paths, st.session_state["current_index"], 1)
                    st.session_state["current_index"] += 1
            with col2:
                if st.button("👎 Dislike"):
                    save_preference(user_data, username, features, images_paths, st.session_state["current_index"], 0)
                    st.session_state["current_index"] += 1
        else:
            st.info("Toutes les images ont été vues. Vous pouvez recommencer.")

# Sauvegarder les préférences utilisateur
def save_preference(user_data, username, features, images_paths, index, label):
    user_data[username]["features"].append(features[index].tolist())
    user_data[username]["labels"].append(label)
    save_user_data(user_data)

if __name__ == "__main__":
    main()