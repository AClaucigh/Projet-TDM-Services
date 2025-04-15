# color-analyzer/main.py
import json
import os
import numpy as np
from PIL import Image, ExifTags
from sklearn.cluster import KMeans
from PIL.ExifTags import TAGS
from fractions import Fraction as IFDRational

def get_metadata(image_path):
    try:
        with Image.open(image_path) as img:
            metadata = {"format": img.format, "size": img.size, "mode": img.mode}
            exif = img._getexif()
            if exif:
                for tag, val in exif.items():
                    name = TAGS.get(tag, tag)
                    if isinstance(val, tuple):
                        metadata[name] = tuple(float(v) if isinstance(v, IFDRational) else v for v in val)
                    elif isinstance(val, IFDRational):
                        metadata[name] = float(val)
                    else:
                        metadata[name] = val
            return metadata
    except:
        return {}

def get_dominant_colors(image_path, num_colors=4):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB").resize((100, 100))
            pixels = np.array(img).reshape(-1, 3)
            sample = pixels[np.random.choice(len(pixels), min(5000, len(pixels)), replace=False)]
            kmeans = KMeans(n_clusters=num_colors)
            kmeans.fit(sample)
            return ["#%02x%02x%02x" % tuple(map(int, center)) for center in kmeans.cluster_centers_]
    except:
        return []

def main():
    with open("data/ville_metadata.json", "r", encoding="utf-8") as f:
        villes = json.load(f)

    results = []
    for ville in villes:
        image_path = ville.get("local_path")
        if os.path.exists(image_path):
            metadata = get_metadata(image_path)
            colors = get_dominant_colors(image_path)
            ville["photo"] = {
                "url": ville["image"],
                "local_path": image_path,
                "metadata": metadata,
                "couleurs_principales": colors
            }
            del ville["image"]
            results.append(ville)

    with open("data/ville_images.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
