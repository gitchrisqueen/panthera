
# TODO: Implement the main application logic. [Milestone: MVP]

from flask import Flask
from config import Config
from models import db
from routes import register_routes
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000)