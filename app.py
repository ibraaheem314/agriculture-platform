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
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

# Charger les variables d'environnement depuis .env
load_dotenv()
airvisual_api_key = os.getenv("AIRVISUAL_API_KEY")
openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

app = Flask(__name__)

# Clés API
app.secret_key = "AGRI3.1415@"
OPENWEATHER_API_KEY = "1707374d07315cd524c6e04d0b0b734b"
AIRVISUAL_API_KEY = "b9d331a5-0c64-42ef-84ca-53779858964d"

# Configuration de la base de données SQLite

app.config['UPLOAD_FOLDER'] = 'uploads'
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

# Connexion à la base de données
def get_db_connection():
    conn = sqlite3.connect('AgriHelper.db')
    conn.row_factory = sqlite3.Row
    return conn

# Route pour la page d'accueil
@app.route("/", methods=["GET", "POST"])
def home():
    return render_template("index.html")

# Route pour about
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact_form", methods=["GET", "POST"])
def contact_form():
    if request.method == "POST":
        # Traiter le formulaire de contact
        flash("Votre message a été envoyé avec succès.", "success")
        return redirect(url_for("contact_success"))
    return render_template("contact_form.html")

@app.route("/contact_success")
def contact_success():
    return render_template("contact_success.html")

@app.route("/error")
def error():
    return render_template("error.html"), 404

# Routes utilisateur
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Logique de connexion
        flash("Connexion réussie !", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Logique d'inscription
        flash("Inscription réussie ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("home"))

# Fonctions utilitaires
def fetch_soil_data(lat, lon):
    try:
        url = f"https://rest.soilgrids.org/query?lon={lon}&lat={lat}&attributes=clay"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            clay_content = data["properties"]["layers"][0]["clay"]  # Teneur en argile
            return {"clay_content": clay_content}
        else:
            print(f"Erreur lors de la récupération des données sur les sols : {response.status_code}")
            return {"error": "Impossible de récupérer les données sur les sols."}
    except Exception as e:
        print(f"Erreur inattendue : {e}")
        return {"error": "Une erreur est survenue lors de la récupération des données."}

def fetch_weather_data(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            "temperature": f"{data['main']['temp']}°C",
            "description": data["weather"][0]["description"],
            "humidity": f"{data['main']['humidity']}%",
            "wind_speed": f"{data['wind']['speed']} m/s",
        }
    else:
        return {"error": "Impossible de récupérer les données météo."}

def fetch_pollution_data(lat, lon):
    url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={AIRVISUAL_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            "aqi": data["data"]["current"]["pollution"]["aqius"],
            "quality": data["data"]["current"]["pollution"]["mainus"]
        }
    else:
        return {"error": "Impossible de récupérer les données de pollution."}

# Route prévisions météo et pollution
@app.route("/weather", methods=["GET", "POST"])
def weather():
    default_city = "Kolda"
    if request.method == "POST":
        city = request.form.get("city", default_city).strip()
    else:
        city = default_city

    # Récupérer les coordonnées géographiques de la ville via OpenWeatherMap
    geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
    response = requests.get(geocoding_url)
    if response.status_code == 200 and response.json():
        location = response.json()[0]
        lat, lon = location["lat"], location["lon"]

        # Récupérer les données météo
        weather_data = fetch_weather_data(lat, lon)
        weather_data["city"] = city  # Ajouter le nom de la ville aux données

        # Récupérer les données de pollution
        pollution_data = fetch_pollution_data(lat, lon)
        pollution_data["city"] = city  # Ajouter le nom de la ville aux données
    else:
        weather_data = {"error": "Ville non trouvée. Veuillez réessayer."}
        pollution_data = {"error": "Ville non trouvée. Veuillez réessayer."}

    return render_template("weather.html", weather_data=weather_data, pollution_data=pollution_data, default_city=default_city)


# Route pour la typologie des sols
@app.route("/typologie-sols", methods=["GET", "POST"])
def typologie_sols():
    default_city = "Kolda"
    if request.method == "POST":
        city = request.form.get("city", default_city).strip()
    else:
        city = default_city

    # Récupérer les coordonnées géographiques de la ville via OpenWeatherMap
    geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
    response = requests.get(geocoding_url)
    if response.status_code == 200 and response.json():
        location = response.json()[0]
        lat, lon = location["lat"], location["lon"]
        soil_data = fetch_soil_data(lat, lon)
        soil_data["city"] = city  # Ajouter le nom de la ville aux données
    else:
        soil_data = {"error": "Ville non trouvée. Veuillez réessayer."}

    return render_template("typologie_sols.html", soil_data=soil_data, default_city=default_city)


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
                    "api_key": "votre_cle_api_plant_id",
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

# ChatBot
HUGGINGFACE_API_KEY = "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"
API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"

tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")

# API pour le chatbot avec Hugging Face
@app.route("/agribot", methods=["GET", "POST"])
def agribot():
    if request.method == "POST":
        # Récupérer la question de l'utilisateur
        user_question = request.form.get("question", "").strip()
        if not user_question:
            return jsonify({"error": "Veuillez poser une question."}), 400

        # Appeler l'API Hugging Face
        try:
            headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
            payload = {
                "inputs": f"Réponds en français : {user_question}",
                "parameters": {
                    "max_length": 100,
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }
            response = requests.post(API_URL, headers=headers, json=payload)
            result = response.json()

            if "error" in result:
                return jsonify({"error": result["error"]}), 500

            return jsonify({"response": result[0]["generated_text"]})
        except Exception as e:
            return jsonify({"error": f"Erreur lors de l'appel à l'API : {str(e)}"}), 500

    # Si la méthode est GET, afficher la page HTML
    return render_template("agribot.html")

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

# Route pour le Tableau de Bord
@app.route("/dashboard")
def user_dashboard():
    if not session.get("user_id"):
        flash("Vous devez être connecté pour accéder au tableau de bord.", "danger")
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("home"))
    return render_template("admin_dashboard.html")

# Route pour le Profil
@app.route("/profile", methods=["GET", "POST"])
def user_profile():
    if not session.get("user_id"):
        flash("Vous devez être connecté pour accéder à votre profil.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        region = request.form.get("region")
        crop_type = request.form.get("crop_type")

        conn.execute("UPDATE users SET username = ?, email = ?, region = ?, crop_type = ? WHERE id = ?",
                     (username, email, region, crop_type, session["user_id"]))
        conn.commit()
        conn.close()

        flash("Profil mis à jour avec succès.", "success")
        return redirect(url_for("user_profile"))

    return render_template("profile.html", user=user)

# Profil administrateur (si applicable)
@app.route("/admin/profile", methods=["GET", "POST"])
def admin_profile():
    if not session.get("admin"):
        flash("Accès réservé aux administrateurs.", "danger")
        return redirect(url_for("home"))

    # Logique spécifique au profil administrateur
    return render_template("admin_profile.html")

# Alerte météo
@app.route("/send_weather_alert", methods=["POST"])
def send_weather_alert():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401

    # Simuler une alerte météo
    notification = {
        "title": "Alerte Météo",
        "message": "Pluie excessive prévue demain. Protégez vos cultures.",
    }

    # Stocker la notification dans la base de données
    conn = get_db_connection()
    conn.execute("INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
                 (user_id, notification["title"], notification["message"]))
    conn.commit()
    conn.close()

    return jsonify({"success": "Notification envoyée"})

@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html"), 404

if __name__ == "__main__":
    # Créer le dossier d'upload s'il n'existe pas
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)