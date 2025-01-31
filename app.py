from flask import Flask, render_template, request, redirect, url_for
import requests
from dotenv import load_dotenv
import os
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

# Charger les variables d'environnement depuis .env
load_dotenv()
airvisual_api_key = os.getenv("AIRVISUAL_API_KEY")
openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
# Initialiser l'application Flask
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

# Route pour le tableau de bord
@app.route("/dashboard")
def dashboard():
    queries = UserQuery.query.all()
    return render_template("dashboard.html", queries=queries)

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
            subject="Alerte AgriHelper", 
            sender=app.config['MAIL_USERNAME'], 
            body=message 
        )
        mail.send(msg) 
        print(f"Email envoyé à {email}")
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)