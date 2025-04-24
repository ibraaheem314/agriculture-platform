# File: app/routes.py
import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, flash, current_app
from flask_mail import Message
from dotenv import load_dotenv
import requests
import sqlite3
import base64

# Charger les variables d'environnement
load_dotenv()

# Blueprint
main = Blueprint('main', __name__)

# Clés API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
AIRVISUAL_API_KEY = os.getenv("AIRVISUAL_API_KEY")
PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUG2")
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

@main.route("/", methods=["GET", "POST"])
def home():
    return render_template("index.html")


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/articles")
def articles():
    articles = [
        {'id': 1, 'title': 'Agriculture durable', 'image': 'images/article1.jpg', 'summary': 'Résumé A'},
        {'id': 2, 'title': 'Gestion de la sécheresse', 'image': 'images/article2.jpg', 'summary': 'Résumé B'}
    ]
    return render_template("articles.html", articles=articles, page=1, total_pages=1)


@main.route("/article/<int:id>")
def article_detail(id):
    article = {
        'id': id,
        'title': f'Article {id}',
        'content': 'Contenu complet de l\'article...',
        'published_at': '2025-04-23',
        'author': 'Auteur'
    }
    return render_template("article_detail.html", article=article, related=[])


@main.route("/communaute")
def communaute():
    discussions = [{'title': 'Rendement du maïs ?', 'author': 'Jean', 'date': '2025-04-22'}]
    return render_template("communaute.html", discussions=discussions)


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
        flash("Message envoyé !", "success")
        return redirect(url_for("main.home"))
    return render_template("contact_form.html")


@main.route("/search")
def search():
    query = request.args.get("q")
    return render_template("search_results.html", query=query)


# ========================
# 📌 Pages dynamiques
# ========================

@main.route("/agribot", methods=["GET", "POST"])
def agribot():
    if request.method == "POST":
        user_question = request.form.get("question", "").strip()
        if not user_question:
            return jsonify({"error": "Veuillez poser une question."}), 400

        # Prompt amical et conversationnel
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        prompt = f"Tu es AgriBot, un assistant sympathique en agriculture. Réponds en français, naturellement et de manière utile.\n\nUtilisateur : {user_question}\nAgriBot :"
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.9
            }
        }

        try:
            response = requests.post("https://api-inference.huggingface.co/models/google/flan-t5-base", headers=headers, json=payload)
            result = response.json()

            if "error" in result:
                return jsonify({"error": result["error"]}), 500

            # Extraire proprement la réponse
            bot_response = result[0]["generated_text"].split("AgriBot :")[-1].strip()
            return jsonify({"response": bot_response})
        except Exception as e:
            return jsonify({"error": f"Erreur lors de l'appel à l'API : {str(e)}"}), 500

    return render_template("agribot.html")



@main.route("/weather", methods=["GET", "POST"])
def weather():
    city = request.form.get("city", "Kolda") if request.method == "POST" else "Kolda"
    geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
    geo_resp = requests.get(geo_url)

    if geo_resp.ok and geo_resp.json():
        loc = geo_resp.json()[0]
        lat, lon = loc["lat"], loc["lon"]

        # Météo
        w_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        w = requests.get(w_url).json()

        # Pollution
        p_url = f"https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={AIRVISUAL_API_KEY}"
        p = requests.get(p_url).json()

        weather_data = {
            "temperature": f"{w['main']['temp']}°C",
            "description": w["weather"][0]["description"],
            "humidity": f"{w['main']['humidity']}%",
            "wind_speed": f"{w['wind']['speed']} m/s",
            "city": city
        }
        pollution_data = {
            "aqi": p["data"]["current"]["pollution"]["aqius"],
            "quality": p["data"]["current"]["pollution"]["mainus"],
            "city": city
        }
    else:
        weather_data = {"error": "Ville inconnue."}
        pollution_data = {"error": "Ville inconnue."}

    return render_template("weather.html", weather_data=weather_data, pollution_data=pollution_data, default_city=city)


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
