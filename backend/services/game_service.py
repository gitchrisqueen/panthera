
# TODO: Implement game-related services. [Milestone: Business Logic]

from models import db
from models.game import Game

class GameService:
    @staticmethod
    def get_all_games():
        return Game.query.all()

    @staticmethod
    def get_past_mlb_games(days=7):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return Game.query.filter(Game.date.between(start_date, end_date)).all()