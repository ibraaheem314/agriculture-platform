# File: app/routes.py
import os
from flask import Blueprint, abort, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from flask_mail import Message
from dotenv import load_dotenv
import requests
import sqlite3
import base64
from datetime import datetime


# Charger les variables d'environnement
load_dotenv()

# Blueprint
main = Blueprint('main', __name__)

# Clés API
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUG2")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
AIRVISUAL_API_KEY = os.getenv("AIRVISUAL_API_KEY")
PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY")
API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"

# Chatbot pipeline (PyTorch, TF disabled via env)
from transformers import pipeline
chatbot_pipeline = pipeline("text-generation", model="sshleifer/tiny-gpt2")

# Database helper
def get_db_connection():
    db_path = os.getenv("DATABASE_URL", "instance/AgriHelper.db").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ========================
# 📌 Routes principales
# ========================
articles = [
    {
        "id": 1,
        "title": "Optimiser l'irrigation avec l'IA",
        "image": "images/irrigation.jpg",
        "summary": "Découvrez comment les algorithmes peuvent prédire les besoins en eau...",
        "content": "<p>Contenu complet de l'article 1 ici...</p>",
        "slug": "optimiser-irrigation-ia",
        "author": "AgriBot",
        "published_at": datetime(2024, 6, 12)
    },
    {
        "id": 2,
        "title": "Typologie des sols : les nouvelles tendances",
        "image": "images/sols.jpg",
        "summary": "Une nouvelle façon d'explorer les sols agricoles...",
        "content": "<p>Contenu complet de l'article 2 ici...</p>",
        "slug": "typologie-sols-tendances",
        "author": "AgriBot",
        "published_at": datetime(2024, 7, 2)
    },
    # Ajoute plus d'articles ici si besoin
]

@main.route("/")
def home():
    return render_template("index.html")

@main.route("/about")
def about():
    return render_template("about.html")


@main.route('/articles')
def articles_list():
    return render_template('blog.html', articles=articles)

@main.route('/article/<int:id>')
def article_detail(id):
    article = next((a for a in articles if a["id"] == id), None)
    if not article:
        abort(404)
    related = [a for a in articles if a["id"] != id][:3]
    breadcrumb = [
        ("Accueil", "main.home", {}),
        ("Articles", "main.articles_list", {}),
        (article["title"], "main.article_detail", {"id": article["id"]})
    ]
    return render_template('article_detail.html', article=article, related=related, breadcrumb=breadcrumb)


@main.route('/communaute', methods=['GET', 'POST'])
def communaute():
    if request.method == 'POST':
        message = request.form.get('message')
        if message:
            post = {
                "user": session.get("username", "Anonyme"),
                "message": message,
                "created_at": datetime.utcnow()
            }
            session.setdefault("posts", []).insert(0, post)  # insère en haut
    posts = session.get("posts", [])
    return render_template("communaute.html", posts=posts)


# ========================
# 📌 Formulaires / Auth
# ========================

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # TODO: Ajouter authentification
        flash("Connexion réussie !", "success")
        return redirect(url_for("main.user_dashboard"))
    return render_template("login.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # TODO: Ajouter enregistrement
        flash("Inscription réussie !", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html")


@main.route("/contact", methods=["GET", "POST"])
def contact_form():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        flash("Merci pour votre message, nous vous répondrons rapidement 🌱", "success")
        return redirect(url_for('main.contact_form'))
    return render_template("contact.html")




@main.route("/search")
def search():
    query = request.args.get("q")
    return render_template("search_results.html", query=query)


# ========================
# 📌 Pages dynamiques
# ========================

# Agribot route

# Initialisation de la mémoire (stockée dans la session utilisateur)
def get_chat_memory():
    if "agribot_memory" not in session:
        session["agribot_memory"] = [
            {"role": "system", "content": "Tu es AgriBot, un assistant agricole francophone expert en IA, en climat et en agriculture durable. Réponds de manière naturelle, polie et utile."}
        ]
    return session["agribot_memory"]

@main.route("/agribot", methods=["GET", "POST"])
def agribot():
    if request.method == "POST":
        try:
            data = request.get_json()
            user_input = data.get("question", "").strip()
        except Exception:
            return jsonify({"error": "Requête invalide."}), 400

        if not user_input:
            return jsonify({"error": "Veuillez poser une question."}), 400

        # Récupération de l'historique
        messages = get_chat_memory()
        messages.append({"role": "user", "content": user_input})

        # Configuration requête
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {os.getenv('OPEN_ROUTER_KEY')}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000"
        }

        payload = {
            "model": "mistralai/mistral-7b-instruct",
            "messages": messages
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and result["choices"]:
                reply = result["choices"][0]["message"]["content"]
                messages.append({"role": "assistant", "content": reply})
                session["agribot_memory"] = messages
                return jsonify({"response": reply})
            else:
                return jsonify({"error": "Réponse vide du modèle."}), 500

        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Erreur réseau : {str(e)}"}), 503
        except Exception as e:
            return jsonify({"error": f"Erreur interne : {str(e)}"}), 500

    return render_template("agribot.html")


# routes.py

main = Blueprint('main', __name__)

# Clés API depuis ton .env
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
AIRVISUAL_API_KEY = os.getenv('AIRVISUAL_API_KEY')

# =========================
# Page météo avec carte interactive
# =========================

@main.route("/weather-map")
def weather_map():
    return render_template("weather_map.html")


# =========================
# API - Météo en temps réel (OpenWeather)
# =========================

@main.route("/api/weather")
def api_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": "Latitude et longitude requises"}), 400

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()

        weather_info = {
            "temperature": round(data["main"]["temp"]),
            "description": data["weather"][0]["description"].capitalize(),
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"]
        }
        return jsonify(weather_info)

    except requests.RequestException as e:
        return jsonify({"error": "Erreur lors de l'accès à l'API météo"}), 500


# =========================
# API - Qualité de l'air en temps réel (AirVisual)
# =========================

@main.route("/api/airquality")
def api_air_quality():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": "Latitude et longitude requises"}), 400

    url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={AIRVISUAL_API_KEY}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()

        aqi = data["data"]["current"]["pollution"]["aqius"]
        return jsonify({"aqi": aqi})

    except requests.RequestException as e:
        return jsonify({"error": "Erreur lors de l'accès à l'API qualité de l'air"}), 500


# =========================
# Ancienne page météo basique (Open-Meteo)
# =========================

@main.route("/weather")
def weather():
    latitude = 48.8566  # Paris par défaut
    longitude = 2.3522

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&current_weather=true&timezone=Europe%2FParis"
    )

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        current_weather = data.get("current_weather", {})
        daily = data.get("daily", {})

        weather_data = {
            "location": "Paris, France",
            "temperature": current_weather.get("temperature"),
            "condition": current_weather.get("weathercode"),
            "humidity": None,  # Non fourni par Open-Meteo
            "wind": current_weather.get("windspeed"),
            "feels_like": None,  # Non fourni
            "alert": None,  # Non fourni
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }

        forecast_data = []
        for i in range(len(daily.get("time", []))):
            forecast_data.append({
                "day": daily["time"][i],
                "temperature": daily["temperature_2m_max"][i],
                "rainfall": daily["precipitation_sum"][i]
            })

        return render_template("weather.html", weather=weather_data, forecast=forecast_data)

    except requests.RequestException as e:
        return render_template("weather.html", weather={}, forecast=[])




@main.route("/soils", methods=["GET", "POST"], endpoint="soils")
def typologie_sols():
    city = request.form.get("city", "Kolda") if request.method == "POST" else "Kolda"
    geo_resp = requests.get(f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}")

    if geo_resp.ok and geo_resp.json():
        loc = geo_resp.json()[0]
        lat, lon = loc["lat"], loc["lon"]
        s = requests.get(f"https://rest.soilgrids.org/query?lon={lon}&lat={lat}&attributes=clay").json()
        clay = s["properties"]["layers"][0]["clay"]
        soil_data = {"clay_content": clay, "city": city}
    else:
        soil_data = {"error": "Ville inconnue."}

    return render_template("typologie_sols.html", soil_data=soil_data, default_city=city)

@main.route('/predict_image', methods=['POST'])
def predict_image():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error':'No file'}),400
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(path)
    img_b64 = base64.b64encode(open(path,'rb').read()).decode()
    resp = requests.post(
        'https://api.plant.id/v2/identify',
        headers={'Content-Type':'application/json'},
        json={
            'api_key':PLANT_ID_API_KEY,
            'images':[f"data:image/jpeg;base64,{img_b64}"],
            'modifiers':['similar_images'],
            'plant_language':'fr',
            'plant_details':['common_names']
        }
    )
    if resp.ok:
        sug = resp.json().get('suggestions',[])
        if sug:
            return jsonify({'class':sug[0].get('plant_name','Unknown')})
    return jsonify({'error':'Identification failed'}),500

@main.route("/account")
def account_portal():
    return render_template("account_portal.html")

@main.route('/blog')
def blog():
    return render_template('blog.html', articles=articles)

@main.route('/coachs')
def coachs():
    coaches = [
        {'name':'Dr. Amadou','specialty':'Agriculture durable'},
        {'name':'Fatou Diarra','specialty':'Gestion des sols'}
    ]
    return render_template('coachs.html', coaches=coaches)

@main.route('/dashboard')
def dashboard_view():
    if not session.get('user_id'):
        flash('Connectez-vous.', 'danger')
        return redirect(url_for('main.login'))
    return render_template('dashboard.html')

@main.route('/profile', methods=['GET','POST'])
def profile_view():
    if not session.get('user_id'):
        flash('Connectez-vous.', 'danger')
        return redirect(url_for('main.login'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
    if request.method=='POST':
        # Update user...
        flash('Profil mis à jour.', 'success')
        return redirect(url_for('main.profile_view'))
    return render_template('profile.html', user=user)

# Error handler in app/__init__.py
