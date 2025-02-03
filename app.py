import requests
from dotenv import load_dotenv
import os
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask import Flask, render_template, request, jsonify, redirect, url_for
import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import base64
from transformers import pipeline

# Charger les variables d'environnement depuis .env
load_dotenv()
airvisual_api_key = os.getenv("AIRVISUAL_API_KEY")
openweather_api_key = os.getenv("OPENWEATHER_API_KEY")


app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = 'uploads'

# Configuration de la base de données SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuration Flask-Mail pour les notifications par email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASS")
mail = Mail(app)

# Modèle de base de données pour stocker les données utilisateur
class UserQuery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    soil_type = db.Column(db.String(50), nullable=False)
    weather_data = db.Column(db.JSON, nullable=True)
    advice = db.Column(db.String(500), nullable=True)

# Route pour la page d'accueil
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        location = request.form.get("location")
        coordinates = request.form.get("coordinates")

        # Validation : Au moins un des deux champs doit être rempli
        if not location and not coordinates:
            return render_template("error.html", message="Veuillez entrer une localisation ou des coordonnées GPS.")

        # Si des coordonnées sont fournies, utilisez-les directement
        if coordinates:
            try:
                lat, lon = map(float, coordinates.split(","))
            except ValueError:
                return render_template("error.html", message="Coordonnées GPS invalides.")
        else:
            # Utiliser une API de géocodage pour obtenir les coordonnées
            url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json"
            headers = {
                "User-Agent": "AgriHelper/1.0"  # Respectez les règles de Nominatim
            }
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200 and response.json():
                    data = response.json()[0]
                    lat, lon = float(data["lat"]), float(data["lon"])
                else:
                    return render_template("error.html", message="Localisation non trouvée. Veuillez vérifier votre saisie.")
            except requests.exceptions.ConnectionError as e:
                return render_template("error.html", message="Impossible de se connecter à l'API de géocodage. Veuillez réessayer plus tard.")

        # Récupérer les données météo, pollution et sols
        weather_data = fetch_weather_data(lat, lon)
        pollution_data = fetch_pollution_data(lat, lon)
        soil_data = fetch_soil_data(lat, lon)

        # Rediriger vers la page détaillée
        return render_template(
            "details.html",
            location=location,
            lat=lat,
            lon=lon,
            weather_data=weather_data,
            pollution_data=pollution_data,
            soil_data=soil_data
        )

    return render_template("index.html")

# Route pour les prévisions météo
@app.route("/meteo-semaine")
def meteo_semaine():
    # Exemple : Récupérer des données météo globales ou par défaut
    weather_data = {
        "city": "Ouagadougou",
        "forecast": [
            {"date": "2023-10-15", "temp": 30, "description": "Ensoleillé"},
            {"date": "2023-10-16", "temp": 28, "description": "Partiellement nuageux"},
        ],
    }
    return render_template("meteo_semaine.html", weather_data=weather_data)

# Route pour les cartes de pollution
@app.route("/pollution")
def pollution():
    # Exemple : Récupérer des données de pollution globales ou par défaut
    pollution_data = {
        "city": "Ouagadougou",
        "aqi": 50,
        "quality": "Bon",
    }
    return render_template("pollution.html", pollution_data=pollution_data)

# Route pour la typologie des sols
@app.route("/typologie-sols")
def typologie_sols():
    # Exemple : Récupérer des données sur les sols globales ou par défaut
    soil_data = {
        "region": "Centre",
        "clay_percentage": 35.6,
        "soil_type": "Argileux",
    }
    return render_template("typologie_sols.html", soil_data=soil_data)

# Route pour about
@app.route("/about")
def about():
    return render_template("about.html")

# Route pour le formulaire de contact
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # Envoyer une notification par email
        send_notification(email, f"Message reçu de {name} : {message}")
        return render_template("contact_success.html")
    return render_template("contact_form.html")

# Fonction pour récupérer les prévisions météo
def fetch_weather_data(lat, lon):
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        daily_forecast = []
        for entry in data["list"]:
            daily_forecast.append({
                "date": entry["dt_txt"],
                "temp": entry["main"]["temp"],
                "description": entry["weather"][0]["description"]
            })
        return daily_forecast
    return None

# Fonction pour récupérer les données de pollution
def fetch_pollution_data(lat, lon):
    api_key = os.getenv("AIRVISUAL_API_KEY")
    url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            "city": data["data"]["city"],
            "aqi": data["data"]["current"]["pollution"]["aqius"],
            "quality": data["data"]["current"]["pollution"]["mainus"]
        }
    return None

# Fonction pour récupérer les données sur les sols
def fetch_soil_data(lat, lon):
    try:
        url = f"https://rest.soilgrids.org/query?lon={lon}&lat={lat}&attributes=clay"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data["properties"]["layers"][0]["clay"]  # Exemple de données
        else:
            print(f"Erreur lors de la récupération des données sur les sols : {response.status_code}")
            return None
    except requests.exceptions.ConnectionError as e:
        print(f"Erreur de connexion : {e}")
        return None
    except Exception as e:
        print(f"Erreur inattendue : {e}")
        return None
    
    
def send_notification(email, message):
    try:
        msg = Message(
            subject="Alerte agrIA", 
            sender=app.config['MAIL_USERNAME'], 
            body=message 
        )
        mail.send(msg) 
        print(f"Email envoyé à {email}")
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")

# agriBot
PLANT_ID_API_KEY = "yZcADod0oIHOJWAaGdxyu66e8CQAMvNShYzprQJsKOSlzBOUF0"
chatbot_pipeline = pipeline("text-generation", model="gpt2")

# Route pour la page AgriBot
@app.route("/agribot")
def agribot():
    return render_template("agribot.html")

# API pour prédire une image avec Plant.id
@app.route("/predict_image", methods=["POST"])
def predict_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Sauvegarder l'image
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # Appeler l'API Plant.id
    try:
        with open(filepath, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode("utf-8")
            response = requests.post(
                "https://api.plant.id/v2/identify",
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": PLANT_ID_API_KEY,
                    "images": [f"data:image/jpeg;base64,{img_data}"],
                    "modifiers": ["similar_images"],
                    "plant_language": "fr",
                    "plant_details": ["common_names", "url"]
                }
            )

        # Vérifier la réponse de l'API
        if response.status_code == 200:
            result = response.json()
            suggestions = result.get("suggestions", [])
            if suggestions:
                plant_name = suggestions[0].get("plant_name", "Plante non identifiée")
                return jsonify({"class": plant_name})
            else:
                return jsonify({"error": "Aucune suggestion trouvée."}), 400
        else:
            return jsonify({"error": f"Erreur API : {response.text}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erreur interne : {str(e)}"}), 500

# API pour le chatbot
from transformers import AutoModelForCausalLM, AutoTokenizer

# Charger le modèle DialoGPT-small
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-small")
chatbot_model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")

@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_input = request.form.get("question")
    if not user_input:
        return jsonify({"error": "No question provided"}), 400

    # Générer une réponse avec DialoGPT-small
    try:
        inputs = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
        outputs = chatbot_model.generate(inputs, max_length=100, pad_token_id=tokenizer.eos_token_id)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la génération de la réponse : {str(e)}"}), 500

# Coachs
@app.route("/coachs")
def coachs():
    # Liste fictive de coachs (remplacez cela par une base de données réelle)
    coaches = [
        {"name": "Dr. Amadou", "specialty": "Agriculture durable", "email": "amadou@example.com"},
        {"name": "Fatou Diarra", "specialty": "Gestion des sols", "email": "fatou@example.com"},
        {"name": "Issa Traoré", "specialty": "Prévisions météo", "email": "issa@example.com"},
    ]
    return render_template("coachs.html", coaches=coaches)

# Communauté
@app.route("/communaute")
def communaute():
    # Exemple de discussions fictives (remplacez cela par une base de données réelle)
    discussions = [
        {"title": "Comment améliorer le rendement du maïs ?", "author": "Jean", "date": "2023-10-10"},
        {"title": "Problème de sécheresse dans ma région", "author": "Fatima", "date": "2023-10-09"},
    ]
    return render_template("communaute.html", discussions=discussions)

# Articles
@app.route("/articles")
def articles():
    # Exemple d'articles fictifs (remplacez cela par une base de données réelle)
    articles = [
        {"title": "Les meilleures pratiques pour l'agriculture durable", "author": "Dr. Amadou", "date": "2023-10-08"},
        {"title": "Comment gérer les sols en cas de sécheresse ?", "author": "Fatou Diarra", "date": "2023-10-07"},
    ]
    return render_template("articles.html", articles=articles)

if __name__ == "__main__":
    # Créer le dossier d'upload s'il n'existe pas
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)