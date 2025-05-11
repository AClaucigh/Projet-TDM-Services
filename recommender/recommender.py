import json
import pika
import numpy as np
import streamlit as st
from sklearn.linear_model import Perceptron
from sklearn.preprocessing import StandardScaler
from PIL import Image
import os

USER_DATA_FILE = "/data/users.json"
TRAINING_THRESHOLD = 5  # Nombre minimum de likes/dislikes avant l'entraînement

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
            images_data.append(ville)
        else:
            break

    connection.close()
    return images_data

# Extraire les caractéristiques enrichies des images
def extract_features(data):
    features, images_paths = [], []
    for entry in data:
        try:
            # Couleurs dominantes
            couleurs_dominantes = [int(c[1:], 16) for c in entry.get("couleurs_dominantes", [])]
            if not couleurs_dominantes:
                raise ValueError("Liste des couleurs dominantes vide.")
            couleur_moyenne = np.mean(couleurs_dominantes)

            # Métadonnées de la ville
            population = entry.get("population", 0)
            superficie = entry.get("superficie", 0)
            pays = hash(entry.get("pays", "unknown")) % 1000  # Encodage simple du pays

            # Extraire les coordonnées géographiques à partir du format WKT
            coordonnees = entry.get("coordonnees", "Point(0 0)")
            if coordonnees.startswith("Point(") and coordonnees.endswith(")"):
                coordonnees = coordonnees[6:-1]  # Supprimer "Point(" et ")"
                longitude, latitude = map(float, coordonnees.split())
            else:
                raise ValueError(f"Format de coordonnées inattendu : {coordonnees}")

            # Histogramme de couleurs (simplifié)
            histogramme_couleurs = np.histogram(couleurs_dominantes, bins=16, range=(0, 16777215))[0]

            # Combiner toutes les caractéristiques
            feature_vector = [
                population,
                superficie,
                couleur_moyenne,
                latitude,
                longitude,
                pays,
                *histogramme_couleurs  # Ajouter l'histogramme de couleurs
            ]
            features.append(feature_vector)
            images_paths.append(entry["image"])
        except Exception as e:
            print(f"Erreur lors de l'extraction des caractéristiques pour l'entrée {entry}: {e}")
            continue  # Ignorer les entrées problématiques

    return np.array(features), images_paths

# Trier les images selon les préférences utilisateur
def sort_images_by_model(model, scaler, features, images_paths):
    # Filtrer les données pour exclure les NaN
    features = filter_nan(features)

    # Standardiser les caractéristiques
    features_std = scaler.transform(features)

    # Prédire les scores pour chaque image
    scores = model.decision_function(features_std)

    # Trier les images par pertinence (scores décroissants)
    sorted_indices = np.argsort(-scores)
    return [images_paths[i] for i in sorted_indices]

# Sauvegarder les préférences utilisateur
def save_preference(user_data, username, features, images_paths, index, label):
    # Ajouter les préférences utilisateur
    user_data[username]["features"].append(features[index].tolist())
    user_data[username]["labels"].append(label)
    save_user_data(user_data)

    # Vérifier si le seuil d'entraînement est atteint
    if len(user_data[username]["labels"]) >= TRAINING_THRESHOLD:
        # Réentraîner le modèle
        X_train = np.array(user_data[username]["features"])
        y_train = np.array(user_data[username]["labels"])

        # Filtrer les données pour exclure les NaN
        X_train, y_train = filter_nan(X_train, y_train)

        # Ajuster le scaler avec les nouvelles données
        st.session_state["scaler"].fit(X_train)

        # Standardiser les caractéristiques
        X_train_std = st.session_state["scaler"].transform(X_train)

        # Réentraîner le modèle
        st.session_state["model"].fit(X_train_std, y_train)
        st.success("Le modèle a été réentraîné avec les nouvelles données.")
    else:
        st.info(f"Encore {TRAINING_THRESHOLD - len(user_data[username]['labels'])} interactions avant le prochain entraînement.")

# Filtrer les données pour exclure les NaN
def filter_nan(features, labels=None):
    mask = ~np.isnan(features).any(axis=1)  # Masque pour exclure les lignes contenant des NaN
    if labels is not None:
        return features[mask], labels[mask]
    return features[mask]

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

        # Extraire les caractéristiques enrichies des images
        features, images_paths = extract_features(images_data)

        # Initialiser le modèle et le scaler
        if "model" not in st.session_state:
            st.session_state["scaler"] = StandardScaler()
            st.session_state["model"] = Perceptron(max_iter=1000, eta0=0.1, random_state=12)

            # Ajuster le scaler avec les caractéristiques enrichies des images
            st.session_state["scaler"].fit(features)

            # Entraîner le modèle initial avec les couleurs préférées
            initial_features = np.array([[0, 0, int(c[1:], 16)] + [0] * (features.shape[1] - 3) for c in user_colors])
            initial_labels = np.ones(len(user_colors))  # Toutes les couleurs préférées sont positives

            # Ajouter des exemples négatifs fictifs
            negative_features = np.zeros((1, features.shape[1]))  # Exemple fictif avec des valeurs nulles
            negative_labels = np.array([0])  # Classe négative

            # Combiner les données positives et négatives
            combined_features = np.vstack((initial_features, negative_features))
            combined_labels = np.hstack((initial_labels, negative_labels))

            # Standardiser les caractéristiques
            combined_features_std = st.session_state["scaler"].transform(combined_features)

            # Entraîner le modèle
            st.session_state["model"].fit(combined_features_std, combined_labels)

        # Trier les images selon le modèle
        sorted_images = sort_images_by_model(st.session_state["model"], st.session_state["scaler"], features, images_paths)

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

if __name__ == "__main__":
    main()