
# TODO: Implement game-related services. [Milestone: Business Logic]

from models import db
from models.game import Game

class GameService:
    @staticmethod
    def get_all_games():
        return Game.query.all()