# collector/main.py
import os
import json
import requests
import shutil
import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

endpoint_url = "https://query.wikidata.org/sparql"
query = """SELECT DISTINCT ?villeLabel ?image ?paysLabel ?population ?superficie ?coordonnees ?fuseauHoraireLabel WHERE { 
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
LIMIT 200"""

def get_results():
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()

def download_image(url, folder="data/images"):
    try:
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, os.path.basename(url))
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, stream=True)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                shutil.copyfileobj(r.raw, f)
            return filename
    except Exception as e:
        print(f"Erreur téléchargement {url}: {e}")
    return None

def resize_image(image_path, max_size=1024):
    from PIL import Image
    try:
        with Image.open(image_path) as img:
            img.thumbnail((max_size, max_size))
            img.save(image_path)
        return image_path
    except:
        return None

def main():
    results = get_results()
    data = []
    for result in results["results"]["bindings"]:
        data.append({
            "ville": result["villeLabel"]["value"],
            "pays": result["paysLabel"]["value"],
            "image": result["image"]["value"],
            "population": int(result["population"]["value"]),
            "superficie": float(result["superficie"]["value"]),
            "coordonnees": result["coordonnees"]["value"],
            "fuseau_horaire": result["fuseauHoraireLabel"]["value"]
        })

    df = pd.DataFrame(data)
    df["local_path"] = df["image"].apply(download_image)
    df["local_path"] = df["local_path"].apply(lambda x: resize_image(x) if x else None)
    df = df[df["local_path"].notna()].reset_index(drop=True)
    df.to_json("data/ville_metadata.json", orient="records", force_ascii=False, indent=4)

if __name__ == "__main__":
    main()
