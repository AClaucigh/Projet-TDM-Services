# Projet-TDM-Services

Contributeurs : GRIVOZ Sophie et CLAUCIGH Alexandre

## Fonctionnement de l'application

![alt text](image.png)

Lors du lancement de l'application, le conteneur "Collector" va télécharger les images de Wikidata correspondant à la requette. 

Une fois les images récupérées, elles sont ensuite placées dans une queue en attendant d'être traitées par le "Procesor". 

Le conteneur "Processor" va assurer la fonction de calcul des couleurs principales des images avant de les placer dans une nouvelle queue et ainsi les mettre à disposition du "Recommender". 

Le conteneur "Recommender" va s'occuper de proposer des images à l'utilisateur qui correspondront à ses gouts. Pour ce faire il implémente un algorithme de recommandation basé sur les Perceptrons. 

L'utilisateur quant à lui va intéreagir avec les images qui lui sont proposées et en fonction de ces réponses, d'autres images lui seront proposées par le "Recommender". 


## Accéder à l'application

Après avoir démarré les conteneurs (**docker compose up --build**) il est possible d'accéder à l'interface web de l'application **uniquement lorsque le processor à fini de calculer les couleurs dominantes des premières images et qu'il les a mis dans la queue**. Ce processus peut prendre plusieurs minutes. Exemple de log lorsque ce processus est terminé : 

```
processor-1    | [Processor] Données publiées dans la file : Louisbourg
processor-1    | [Processor] Reçu : Ljubljana
processor-1    | [Processor] Fichier ville_metadata.json mis à jour pour Ljubljana
```

A noter qu'il est probable qu'il y ait parfois des logs d'erreurs (erreurs gérées par l'application) qui apparaissent dans la console. Cela est du au fait que parmi le grand nombre de données récoltées, il est difficile d'anticiper tous les cas de figure possible. Cependant, cela ne gène en rien le bon fonctionnement de l'application.

Pour se connecter à l'application, il faut se connecter au **port 8501** de la machine (**localhost:8501**). On doit ensuite renseigner un nom d'utilisateur ainsi que des couleurs favorites au format hexadécimal. Exemples de couleurs préférées :

- #4465C2,#E37C20,#703D20,#BDC8F6

- #817C5C,#4E5B61,#657739,#020308


## Comportement de l'application

Lors de la connexion à l'application, le modèle est initialisé avec les couleurs préférées de l'utilisateur. Les premières images lui sont alors proposées.

Après les 5 premières interactions, chaque like/dislike déclenche le ré-entrainelent du modèle.

Les images sont triées dynamiquement en fonction des préférences utilisateur, et les plus pertinentes sont affichées en premier.


## A noter

Le fichier du volume partagé contenant les utilisateurs et leurs préférences est users.json.

Le fichier des villes présent dans le volume partagé, ville_metadata.json, est le fichier où sont enregistrées les données des villes puis leurs couleurs dominantes. Cela à été mis en place pour mieux comprendre ce qui transite dans les queues, mais **les queues ne se basent pas sur ce fichier**.


## Commandes utiles 

### Démarrer le projet 

> docker-compose up --build

### Etteindre les conteneurs 

> docker-compose down -v 

### Supprimer les volumes des conteneurs 

> docker system prune -a --volumes


## Lien vers le git 

https://github.com/AClaucigh/Projet-TDM-Services.git