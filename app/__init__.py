# app/__init__.py
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__)     # prendra app/templates et app/static par défaut

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY','AGRI3.1415@')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', f"sqlite:///{os.path.dirname(__file__)}/instance/AgriHelper.db"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Mail config…
    app.config['MAIL_SERVER']='smtp.gmail.com'
    app.config['MAIL_PORT']=587
    app.config['MAIL_USE_TLS']=True
    app.config['MAIL_USERNAME']=os.getenv('EMAIL_USER')
    app.config['MAIL_PASSWORD']=os.getenv('EMAIL_PASS')

    db.init_app(app)
    mail.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html'), 404

    return app
