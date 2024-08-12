
# TODO: Define the Game model. [Milestone: Database Schema]

from . import db

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    team_home = db.Column(db.String(50), nullable=False)
    team_away = db.Column(db.String(50), nullable=False)
    score_home = db.Column(db.Integer)
    score_away = db.Column(db.Integer)