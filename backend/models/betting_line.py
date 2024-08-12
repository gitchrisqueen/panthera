
# TODO: Define the BettingLine model. [Milestone: Database Schema]

from . import db

class BettingLine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    line = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)