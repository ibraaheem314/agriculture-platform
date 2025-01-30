from flask import Flask, render_template, request, redirect, url_for
import requests
from dotenv import load_dotenv
import os
from utils.weather_utils import fetch_weather_data
from utils.soil_utils import analyze_soil
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

from dotenv import load_dotenv
import os

# Charger les variables d'environnement depuis .env
load_dotenv()

# Récupérer la clé API
API_KEY = os.getenv("API_KEY")

app = Flask(__name__)

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
        soil_type = request.form.get("soil_type")

        # Récupérer les données météo
        weather_data = fetch_weather_data(location)
        if not weather_data:
            return render_template("index.html", error="Impossible de récupérer les données météo.")

        # Analyser le sol
        advice = analyze_soil(soil_type)

        # Enregistrer les données dans la base de données
        new_query = UserQuery(location=location, soil_type=soil_type, weather_data=weather_data, advice=advice)
        db.session.add(new_query)
        db.session.commit()

        # Rediriger vers le tableau de bord
        return redirect(url_for("dashboard"))

    return render_template("index.html")

# Route pour le tableau de bord
@app.route("/dashboard")
def dashboard():
    queries = UserQuery.query.all()
    return render_template("dashboard.html", queries=queries)

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

# Route pour les prévisions météo semaine
@app.route("/meteo-semaine", methods=["GET"])
def meteo_semaine():
    location = request.args.get("location")
    if location:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            weather_data = response.json()
            daily_forecast = []
            for entry in weather_data["list"]:
                daily_forecast.append({
                    "date": entry["dt_txt"],
                    "temp": entry["main"]["temp"],
                    "description": entry["weather"][0]["description"]
                })
            return render_template("meteo_semaine.html", location=location, weather_data=daily_forecast)
        else:
            error_message = f"Erreur {response.status_code} : Impossible de récupérer les données météo."
            return render_template("meteo_semaine.html", error=error_message)
    return render_template("meteo_semaine.html", error="Veuillez entrer une localisation.")

# Route pour les données de pollution
@app.route("/pollution", endpoint="pollution_data")
def pollution():
    try:
        url = "https://api.airvisual.com/v2/nearest_city?key=votre_cle_api_airvisual"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            pollution_data = {
                "city": data["data"]["city"],
                "aqi": data["data"]["current"]["pollution"]["aqius"],
                "quality": data["data"]["current"]["pollution"]["mainus"]
            }
            return render_template("pollution.html", pollution_data=pollution_data)
        else:
            error_message = f"Erreur {response.status_code} : Impossible de récupérer les données de pollution."
            return render_template("pollution.html", error=error_message)
    except Exception as e:
        print(f"Erreur lors de la récupération des données de pollution : {e}")
        return render_template("pollution.html", error="Une erreur s'est produite.")
# Route pour la typologie des sols
@app.route("/typologie-sols")
def typologie_sols():
    lat, lon = 12.372365, -1.628863  # Coordonnées du Burkina Faso
    url = f"https://rest.soilgrids.org/query?lon={lon}&lat={lat}&attributes=clay"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        soil_type = data["properties"]["layers"][0]["clay"]  # Exemple de données
        return render_template("typologie_sols.html", soil_type=soil_type)
    return render_template("typologie_sols.html", error="Impossible de récupérer les données sur les sols.")

# Fonction pour envoyer des notifications par email
def send_notification(email, message):
    try:
        msg = Message(
            subject="Alerte AgriHelper",  # Objet de l'email
            sender=app.config['MAIL_USERNAME'],  # Expéditeur
            recipients=[email],  # Destinataire(s)
            body=message  # Contenu du message
        )
        mail.send(msg)  # Envoyer l'email
        print(f"Email envoyé à {email}")
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")


import logging

logging.basicConfig(level=logging.DEBUG)

@app.route("/pollution")
def pollution():
    try:
        url = "https://api.airvisual.com/v2/nearest_city?key=votre_cle_api_airvisual"
        response = requests.get(url)
        logging.debug(f"Réponse de l'API AirVisual : {response.status_code}, {response.text}")
        if response.status_code == 200:
            data = response.json()
            pollution_data = {
                "city": data["data"]["city"],
                "aqi": data["data"]["current"]["pollution"]["aqius"],
                "quality": data["data"]["current"]["pollution"]["mainus"]
            }
            return render_template("pollution.html", pollution_data=pollution_data)
        else:
            error_message = f"Erreur {response.status_code} : Impossible de récupérer les données de pollution."
            return render_template("pollution.html", error=error_message)
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des données de pollution : {e}")
        return render_template("pollution.html", error="Une erreur s'est produite.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Créer la base de données si elle n'existe pas
    app.run(debug=True)