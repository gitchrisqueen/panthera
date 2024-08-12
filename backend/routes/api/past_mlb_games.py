#  Copyright (c) 2024. Christopher Queen Consulting LLC (http://www.ChristopherQueenConsulting.com/)

from flask import Blueprint, jsonify
from services.game_service import GameService

past_mlb_games_bp = Blueprint('past_mlb_games', __name__)

@past_mlb_games_bp.route('/api/past-mlb-games', methods=['GET'])
def get_past_mlb_games():
    games = GameService.get_past_mlb_games()
    return jsonify([game.to_dict() for game in games])