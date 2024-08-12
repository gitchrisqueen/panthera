from models import db
from models.betting_line import BettingLine

class BettingLineService:
    @staticmethod
    def get_all_lines():
        return BettingLine.query.all()