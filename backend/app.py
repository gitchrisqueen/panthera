from flask import Flask
from config import Config
from models import db
from routes import register_routes

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
register_routes(app)

if __name__ == "__main__":
    app.run()